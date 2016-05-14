"""
functions for performing short term archiving
"""

from XML.standard_module_setup import *
from CIME.case import Case
from CIME.utils import expect, appendStatus
from CIME.XML.env_archive import EnvArchive
from os.path import isfile, isdir, join
import shutil, glob, re

logger = logging.getLogger(__name__)

def check_run(case):
    logger.debug('In check_run...')
    dout_s_root = case.get_value('DOUT_S_ROOT')
    if dout_s_root is None or dout_s_root == 'UNSET':
        expect(False, 'XML variable DOUT_S_ROOT is required for root location of short-term achiver')
    if not isdir(dout_s_root):
        os.makedirs(dout_s_root)
    dout_s_save_interim = case.get_value('DOUT_S_SAVE_INTERIM_RESTART_FILES')
    if dout_s_save_interim == 'FALSE' or dout_s_save_interim == 'UNSET':
        rest_n = int(case.get_value('REST_N'))
        stop_n = int(case.get_value('STOP_N'))
        if rest_n < stop_n:
            logger.warn('Restart files from end of run will be saved, interim restart files will be deleted')
    statusFile = 'CaseStatus'
    runComplete = False
    caseroot = case.get_value('CASEROOT')
    if isfile(join(caseroot, statusFile)):
        if 'Run SUCCESSFUL' in open(join(caseroot, statusFile)).read():
            runComplete = True
    return runComplete


def list_xml(case, archive):
    logger.debug('In list_xml...')
    for archive_spec_node in archive.get_nodes('comp_archive_spec'):
        comp = archive_spec_node.attrib['name']
        rootdir_node = archive.get_node('rootdir', root=archive_spec_node)
        rootdir = rootdir_node.text
        ninst = case.get_value('NINST_' + rootdir.upper())
        multi = ninst > 1
        logger.info('\n============================================================================')
        logger.info('component name = %s ' % comp)
        logger.info('rootdir = %s' % rootdir)
        logger.info('multiple-instance support = %s ' % multi)
        casename = case.get_value('CASENAME')
        dout_s_root = case.get_value('DOUT_S_ROOT')
        for file_extension in archive.get_nodes('file_extension', root=archive_spec_node):
            suffix = file_extension.attrib['regex_suffix']
            subdir = archive.get_node('subdir', root=file_extension).text
            keep_last_in_rundir = archive.get_node('keep_last_in_rundir', root=file_extension).text
            logger.info('\n  ***** File extension specification')
            logger.info('  regex_suffix = %s ' % suffix)
            logger.info('  subdir = %s ' % join(dout_s_root, rootdir, subdir))
            logger.info('  keep_last_in_rundir %s = ' % keep_last_in_rundir)


def list_archive(dirname):
    logger.debug('In list_archivoe: %s ...' % dirname)
    logger.info('%s ' % dirname)
    if isdir(dirname):
        list_dirs = os.walk(dirname)
        for root, dirs, files in list_dirs:
            for f in files:
                print join(root, f)


def get_datenames(case):
    logger.debug('In get_datename...')
    rundir = case.get_value('RUNDIR')
    expect(isdir(rundir), 'Cannot open directory %s ' % rundir)
    casename = case.get_value("CASE")
    files = sorted(glob.glob(os.path.join(rundir,casename + '.cpl.r*.nc')))
    if not files:
        expect(False, 'Cannot find a %s.cpl.r.*.nc file in directory %s ' % (casename,rundir))
    datenames = []
    for filename in files:
        names = filename.split('.')
        datename = names[-2]
        datenames.append(datename)
        logger.debug('cpl dateName: %s ' % datename)
    return datenames


def move_files(files, case, keep_last_in_rundir, suffix, archive_dir):
    logger.debug('In move_files...')
    rundir = case.get_value('RUNDIR')
    if keep_last_in_rundir:
        keepfile = files[-1]
        shutil.copy(join(rundir, keepfile), join(archive_dir, keepfile))
        logger.debug('keepfile = %s ' % keepfile)
        for filename in files:
            if filename != keepfile and isfile(filename):
                shutil.move(join(rundir, filename), join(archive_dir, filename))
    else:
        for filename in files:
            shutil.move(join(rundir, filename), join(archive_dir, filename))

           
def archive_process(case, archive, datename, datename_is_last):
    logger.debug('In archive_process...')
    dout_s_root = case.get_value('DOUT_S_ROOT')
    rundir = case.get_value('RUNDIR')

    compset_comps = case.get_compset_components()
    compset_comps.append('cpl')

    for archive_spec_node in archive.get_nodes('comp_archive_spec'):
        comp = archive_spec_node.attrib['name']
        comp.split('[')[0]
        if comp not in compset_comps:
            continue

        node = archive.get_node('rootdir', root=archive_spec_node)
        compclass = node.text
        logger.info('doing short term archiving for %s (%s)' % (comp, compclass))

        node = archive.get_node('rpointer_content', root=archive_spec_node)
        rpointer_content = node.text

        if rpointer_content is not None:
            subs = dict()
            subs['datename'] = datename
            subs['casename'] = case.get_value("CASE")
            for key in subs.keys():
                rpointer_content = rpointer_content.replace(key, subs[key])

        #-------------------------------------------------
        # determine ninst and ninst_suffix
        #-------------------------------------------------
        ninst = case.get_value('NINST_' + compclass.upper())
        if ninst is None:
            ninst = 1

        ninst_suffix = []
        for i in range(ninst):
            if ninst > 1:
                ninst_suffix.append('_' + '%04d' % i)
            else:
                ninst_suffix.append('')

        logger.debug("ninst and ninst_suffix are: %s and %s for %s" %(ninst,ninst_suffix,compclass))
        
        #-------------------------------------------------
        # archive history and log files over 
        #-------------------------------------------------
        for file_extension in archive.get_nodes('file_extension', root=archive_spec_node):
            subdir = archive.get_node('subdir', root=file_extension).text
            if subdir == 'rest':
                # handle restart files outside of this loop
                continue

            suffix = file_extension.attrib['regex_suffix']
            keep_last_in_rundir = archive.get_node('keep_last_in_rundir', root=file_extension).text

            archive_dir = os.path.join(dout_s_root,compclass,subdir);
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)
                logger.debug("created directory archive_dir")
            for i in range(ninst):
                newsuffix = suffix
                if subdir == 'logs':
                    newsuffix = compclass + ninst_suffix[i] + suffix
                else:
                    casename = case.get_value('CASE')
                    newsuffix = casename + '.' + comp + ninst_suffix[i] + suffix

                p = re.compile(newsuffix) 
                files = [ f for f in os.listdir(rundir) if p.match(f) ]
                logger.debug("short term archivign suffix is %s " %newsuffix)
                logger.debug("hist/log files are %s " %files)
                if files:
                    move_files(files, case, keep_last_in_rundir, newsuffix, archive_dir)

        #-------------------------------------------------
        # archive restarts and all necessary associated fields (e.g. rpointer files)
        #-------------------------------------------------
        # determine directory for archiving restarts based on datename
        archive_dir = join(dout_s_root, 'rest', datename)
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)

        # move all but latest restart files into the archive restart directory
        # copy latest restart files to archive restart directory
        for file_extension in archive.get_nodes('file_extension', root=archive_spec_node):
            subdir = archive.get_node('subdir', root=file_extension).text
            if subdir != 'rest':
                continue

            suffix = file_extension.attrib['regex_suffix']
            for i in range(ninst):
                pattern = ninst_suffix[i] + ".*" + suffix + datename 
                p = re.compile(pattern) 
                files = [ f for f in os.listdir(rundir) if p.match(f) ]
                for filename in files:
                    restfile = os.path.basename(filename)

                    # Note that the latest file should be copied and not moved
                    if (datename_is_last):
                        shutil.copy(join(rundir,filename), join(archive_dir,restfile))
                        # Add the copy of rpointer files
                        rpointers = glob.glob(os.path.join(rundir,'rpointer.*'))
                        for rpointer in rpointers:
                            shutil.copy(rpointer,os.path.join(archive_dir,os.path.basename(rpointer)))
                    else:
                        dout_s_save_interim = case.get_value('DOUT_S_SAVE_INTERIM_RESTART_FILES')
                        # Only archive intermediate restarts if requested - otherwise remove them
                        if dout_s_save_interim:
                            shutil.move(join(rundir,filename), join(archive_dir,restfile))
                            f = open(os.path.join(archive_dir,'rpointer.'+compclass),'w')
                            for output in rpointer_content.split(','):
                                f.write("%s \n" %output)
                            f.close()
                        else:
                            os.remove(os.path.join(rundir,filename))

                    # archive all history files that are needed on restart
                    restart_hist_varname = archive.get_node("restart_history_varname",root=archive_spec_node).text
                    if restart_hist_varname != 'unset':
                        cmd = "ncdump -v %s %s " %(restart_hist_varname, restfile) 
                        rc,out,error = run_cmd(cmd, ok_to_fail=True)
                        searchname = "%s =" %restart_hist_varname
                        offset = out.index(searchname)
                        items  = out[offset:].split(",")
                        for item in items:
                            matchobj = re.search("\"(\w.*)\s?\"",item)
                            if matchobj:
                                print matchobj.group(1).strip() #FIXME - move this file from the archive hist to the archive/rest/datename


def short_term_archive(input_flag, output_flag, undo_flag):
    case = Case()
    caseroot = case.get_value('CASEROOT')
    archive = EnvArchive(infile=os.path.join(caseroot, 'env_archive.xml'))
    rundir = case.get_value('RUNDIR')
    runComplete = check_run(case)
    if input_flag:
        list_xml(case, archive)

    elif output_flag:
        if runComplete:
            dout_s_root = case.get_value('DOUT_S_ROOT')
            logger.info('Short-term archive listing of %s ' % dout_s_root)
            list_archive(dout_s_root)
        else:
            expect(False, 'st_archive: run is not complete')

    elif undo_flag:
        undoArchive(case)

    elif runComplete:
        caseroot = case.get_value('CASEROOT')
        appendStatus('st_archiving starting', caseroot=caseroot, sfile='CaseStatus')

        # get all the unique datenames for the cpl restart files and
        # also find the last one
        datenames = get_datenames(case)
        for datename in datenames:
            datename_is_last = False
            if datename == datenames[-1]:
                datename_is_last = True
            archive_process(case, archive, datename, datename_is_last)

        appendStatus('st_archiving completed', caseroot=caseroot, sfile='CaseStatus')
        logger.info('short term archiving is complete.')

    else:
        expect(False, 'based on CaseStatus output, run is either not complete or was not successful')
