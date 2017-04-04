"""
long term archiving
"""

import shutil, glob, re, os, errno

from CIME.XML.standard_module_setup import *
from CIME.utils                     import expect, does_file_have_string, append_status, run_cmd
from CIME.utils                     import is_last_process_complete
from distutils.spawn                import find_executable

import time

logger = logging.getLogger(__name__)

###############################################################################
def _copy_dirs_hsi(dout_s_root, dout_l_msroot, dout_l_hpss_accnt, dryrun, 
                   dout_l_delete):
###############################################################################

    logger.debug('In copy_dirs_hsi...')

    # intialize run_cmd return codes
    stat = 0
    msg = ''

    # initialize success for return status
    success = False
    
    # check if hsi exists in path
    hsi = find_executable("hsi")
    
    logger.info("hsi: %s " %hsi)
    expect(hsi != None, "lt_archive: asked for copy_dirs_hsi - but hsi not found, check path")
 
    # check to see if copies of local files should be saved or not
    saveFlag="-PRU"
    if dout_l_delete:
        saveFlag="-PRUd"

    os.chdir(dout_s_root)
    logger.info('cwd: %s' %os.getcwd())

    # send files to HPSS
    hsiArgs='"mkdir -p ' + dout_l_msroot + ' ; chmod +t ' + dout_l_msroot + ' ; cd ' + dout_l_msroot + ' ; put ' + saveFlag + ' *"'

    logger.debug('hsiArgs: {0} '.format(hsiArgs))

    hsiCmd = 'hsi ' + hsiArgs

    # check if hpss_accnt is set
    # NOTE - this may not be an optimal check for the HPSS account setting
    if not dout_l_hpss_accnt.startswith('0000'):
        hsiCmd = 'hsi -a ' + dout_l_hpss_accnt + ' ' + hsiArgs

    if dryrun:
        logger.info('dryrun: %s' %hsiCmd)
    else:
        logger.info('running command: %s' %hsiCmd)
        stat,msg,errput = run_cmd(hsiCmd)

    if stat == 0:
        success = True
    
    return success, msg


###############################################################################
def _check_ssh_key(dout_l_ssh_login, dout_l_ssh_mach):
###############################################################################

    ssh_key = True
    # check if ssh key is set for passwordless access to the remote machine
    try:
        output = subprocess.check_output( "ssh -oNumberOfPasswordPrompts=0 {0}@{1} 'echo hello'".format(dout_l_ssh_login,dout_l_ssh_mach), 
                                 stderr=subprocess.STDOUT,
                                 shell=True)
    except subprocess.CalledProcessError as e:
        ssh_key = False
        msg = 'ERROR: unable to connect to remote host {0}@{1}'.format(dout_l_ssh_login,dout_l_ssh_mach)
        msg += '\n sshkeys to the remote login should be setup prior to running lt_archive in mode' \
                    'DOUT_L_MODE=copy_dirs_ssh.'

    return ssh_key, msg

###############################################################################
def cmd_exists(cmd):
###############################################################################
    return subprocess.call("type " + cmd, shell=True, 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

###############################################################################
def _copy_dirs_ssh(dout_s_root, dout_l_msroot, dout_l_ssh_mach, dryrun,
                   dout_l_delete, dout_l_ssh_login):
###############################################################################

    logger.debug('In copy_dirs_ssh...')
    success = True
    msg = ""
    
    # check sshkeys
    ssh_key, msg = check_ssh_key(dout_l_ssh_login, dout_l_ssh_mach):
    if not ssh_key:
        return ssh_key, msg

    src = dout_s_root
    dst = dout_l_ssh_login+'@'+dout_l_ssh_mach
    errors = []

    # check if dst exists; recursively create if does not exists
    if dryrun:
        logger.info('dryrun: make remote dirs %s' %dst)
    else:
        try:
            output = subprocess.check_output( "ssh -q {0} 'mkdir -p {1}'".format(dst,dout_l_msroot), 
                                              stderr=subprocess.STDOUT,
                                              shell=True)
        except subprocess.CalledProcessError as e:
            msg = 'ERROR: unable to access remote directory {0} on remote host {1}. Check permissions'.format(dout_l_msroot,dst)
            return False, msg

    # check if special NASA pleiades scripts exist on the remote machine
    try:

# START HERE with call to cmd_exists on remote machine
        cmd = "ssh -q {0} 'which cxfscp | wc -w'".format(dst)
        output = subprocess.check_output( cmd,
                                          stderr=subprocess.STDOUT,
                                          shell=True)
    except subprocess.CalledProcessError as e:
        msg = 'ERROR: unable to access remote directory {0} on remote host {1}. Check permissions'.format(dout_l_msroot,dst)
        return False, msg


    names = os.listdir(src)
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dout_l_msroot, name)

        try:
            if os.path.isdir(srcname):
                if dryrun:
                    logger.info('dryrun: calling cp -r for %s to %s' %srcname %dstname)
                    if dout_l_delete:
                        logger.info('dryrun: delete dir tree %s' %srcname)
                else:

                    try:

                        output = subprocess.check_output( "ssh -q {0} 'ir -p {1}'".format(dst,dout_l_msroot), 
                                                          stderr=subprocess.STDOUT,
                                                          shell=True)
                    except subprocess.CalledProcessError as e:
                        msg += 'ERROR: unable to access remote directory {0} on remote host {1}. Check permissions'.format(dout_l_msroot,dst)


                        shutil.copytree(srcname, dstname, symlinks, ignore=None)
                        # delete the local directory
                        if dout_l_delete:

                            try:
                                os.rmtree(scrname)
                            except OSError as why:
                                errors.extend((srcname, str(why)))

                    except (IOError, os.error) as why:
                        errors.append((srcname, dstname, str(why)))
            else:
                if dryrun:
                    logger.info('dryrun: calling copy2 for %s to %s' %srcname %dstname)
                    if dout_l_delete:
                        logger.info('dryrun: delete local file %s' %srcname)
                else:

                    try:
                        shutil.copy2(srcname, dstname)
                        # delete the local file
                        if dout_l_delete:
                            try:
                                os.remove(srcname)
                            except OSError as why:
                                errors.extend((srcname, str(why)))
                    except OSError as why:
                        errors.extend((srcname, dstname, str(why)))

        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        except Error as err:
            errors.extend(err.args[0])

    try:
        if dryrun:
            logger.info('dryrun: calling copystat for %s to %s' %src %dst)
        else:
            shutil.copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))

    if errors:
        msg = Error(errors)
        success = False

    return success, msg


###############################################################################
def _copy_dirs_local(dout_s_root, dout_l_msroot, dryrun, dout_l_delete):
###############################################################################

    logger.debug('In copy_dirs_local...')
    success = True
    msg = ""
    
    src = dout_s_root
    dst = dout_l_msroot
    errors = []

    # check if dst exists; recursively create if exists
    if not os.path.exists(dst):
        if dryrun:
            logger.info('dryrun: makedirs %s' %dst)
        else:
            os.makedirs(dst)

    names = os.listdir(src)
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                if dryrun:
                    logger.info('dryrun: create symlink %s -> %s' %linkto %dstname)
                else:
                    os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                if dryrun:
                    logger.info('dryrun: calling copytree for %s to %s' %srcname %dstname)
                    if dout_l_delete:
                        logger.info('dryrun: delete dir tree %s' %srcname)
                else:

                    try:
                        shutil.copytree(srcname, dstname, symlinks, ignore=None)
                        # delete the local directory
                        if dout_l_delete:

                            try:
                                os.rmtree(scrname)
                            except OSError as why:
                                errors.extend((srcname, str(why)))

                    except (IOError, os.error) as why:
                        errors.append((srcname, dstname, str(why)))
            else:
                if dryrun:
                    logger.info('dryrun: calling copy2 for %s to %s' %srcname %dstname)
                    if dout_l_delete:
                        logger.info('dryrun: delete local file %s' %srcname)
                else:

                    try:
                        shutil.copy2(srcname, dstname)
                        # delete the local file
                        if dout_l_delete:
                            try:
                                os.remove(srcname)
                            except OSError as why:
                                errors.extend((srcname, str(why)))
                    except OSError as why:
                        errors.extend((srcname, dstname, str(why)))

        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        except Error as err:
            errors.extend(err.args[0])

    try:
        if dryrun:
            logger.info('dryrun: calling copystat for %s to %s' %src %dst)
        else:
            shutil.copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))

    if errors:
        msg = Error(errors)
        success = False

    return success, msg


###############################################################################
def case_lt_archive(case, dryrun, force):
###############################################################################
    """"
    perform long term archiving of DOUT_S_ROOT files to HPSS
    """
    caseroot = case.get_value("CASEROOT")

    # max number of threads needed by scripts
    os.environ["maxthrds"] = "1"

    # document start
    append_status("lt_archive starting",caseroot=caseroot,sfile="CaseStatus")
    logger.info("lt_archive starting")

    # determine status of short term archiving 
    staComplete = is_last_process_complete(os.path.join(caseroot, "CaseStatus"),
                                           "st_archiving completed", "st_archiving started")
    logger.info("staComplete : {0}".format(staComplete))

    # get env variables and call the different archive methods based on mode
    if staComplete or force:
        dout_s_root = case.get_value("DOUT_S_ROOT")
        dout_l_msroot = case.get_value("DOUT_L_MSROOT")
        dout_l_hpss_accnt = case.get_value("DOUT_L_HPSS_ACCNT")
        dout_l_mode = case.get_value("DOUT_L_MODE")
        dout_l_delete = case.get_value("DOUT_L_DELETE_LOCAL_FILES")
        dout_l_ssh_mach = case.get_value("DOUT_L_SSH_MACHINE")
        dout_l_ssh_login = case.get_value("DOUT_L_SSH_LOGINNAME")
        lid = time.strftime("%y%m%d-%H%M%S")

        msg = ""

        # check if dout_s_root  exists
        if not os.path.exists(dout_s_root):
            expect(False, "lt_archive: DOUT_S_ROOT = '%s' does not exist" %dout_s_root)

        # perform archiving based on the mode requested
        if dout_l_mode == "copy_dirs_hsi":
           (success, msg) = _copy_dirs_hsi(dout_s_root, dout_l_msroot, dout_l_hpss_accnt, 
                                           dryrun, dout_l_delete)
        elif dout_l_mode == "copy_dirs_ssh":
           (success, msg) = _copy_dirs_ssh(dout_s_root, dout_l_msroot, dout_l_ssh_mach,
                                           dryrun, dout_l_delete, dout_l_ssh_login)
        elif dout_l_mode == "copy_dirs_local":
           (success, msg) = _copy_dirs_local(dout_s_root, dout_l_msroot, dryrun, dout_l_delete)
        else:
            expect(False,
                   "lt_archive: unrecognized DOUT_L_MODE '"+dout_l_mode+"'."
                   "Unable to perform long term archive...")

        if not success:
            expect(False,
                   "lt_archive: "+msg+
                   "Unable to perform long term archive...")

    else:
        expect(False,
               "lt_archive: run or st_archive is not yet complete or was not successful."
               "Unable to perform long term archive...")

    # document completion
    append_status("lt_archive completed" ,caseroot=caseroot, sfile="CaseStatus")
    logger.info("lt_archive completed")

    return True
