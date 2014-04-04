#!/usr/bin/python

# Script to align dependencies in a "*.gradle" file with versions in a BOM
# Can pass in a single .gradle file to update with the '-l' option
# If no '-l' option is supplied, all *.gradle files will be updated recursively
# under the current directory.

import argparse
import logging
import os
import os.path
import re
import shutil
import urllib
import xml.etree.ElementTree as ET

# Set up global variables
logging_dir = "alignment_logs"

def main():
    libs = []
    
    parser = argparse.ArgumentParser(description=
                                     'Align gradle libraries file with a BOM.')
    
    parser.add_argument('-b', '--bom', dest='bom',
                         required=True, help='The bom to align with')
    parser.add_argument('-l', '--lib', dest='lib',
                         required=False, help='The libraries file to update')
    args = parser.parse_args()  

    bom = args.bom
    libs.append(args.lib)
    
    return(bom, libs)

def get_bom_from_url(bom):
    m = re.match(r'.*/(.*)$',bom)
    pid = str(os.getpid())
    bom_name = m.group(1)
    outfile = "/tmp/" + bom_name + "." + pid

    urllib.urlretrieve(bom, filename=outfile)
     
    return(outfile)    

def get_properties_node(node, node_name):
    if node.findall('*'):
        for n in node.findall('*'):
            if node_name in n.tag:
                return n

def parse_bom(params): 
    tree = ET.parse(params)
    root = tree.getroot()  
    
    properties_node = get_properties_node(root, 'properties')
    prop = {}

    for child in properties_node.findall('*'):
        key = re.sub(r'{.*}|version\.','',child.tag)
        val = child.text

        if val and key:
            prop[key] = val
    
    return prop
                
def parse_lib(lib_files, bom_properties):
    if not (os.path.exists(logging_dir)):
        _mkdir(logging_dir)

    # Setup logging
    mod_logger = logging.getLogger('1')
    mod_logger.setLevel(logging.INFO)
    mod_logger.addHandler(logging.FileHandler(logging_dir + '/mod.log','w'))
    mod_logger.info("Modified Versions\n----------------------------")

    missing_logger = logging.getLogger('2')
    missing_logger.setLevel(logging.INFO)
    missing_logger.addHandler(logging.FileHandler(logging_dir + '/missing.log','w'))    
    missing_logger.info("Not in BOM\n----------------------------")
        
    for lib_file in lib_files:
        lib_file = re.sub(r'^\.\/','',lib_file)
        if (re.search(r'\/', lib_file)):
            m = re.match(r"(.*)(\/.*\.gradle$)",lib_file)
            _mkdir(logging_dir + "/" + m.group(1))
            
        shutil.copyfile(lib_file, logging_dir +
                    "/" + lib_file + ".orig")
        f = open(lib_file, 'r')
        output = open(lib_file + ".mod", 'w')
        group = ""

        # Clear header flags        
        missing_header = ""
        mod_header = ""
    
        for line in f:
            m = ""
            group = ""
            version = ""
            
            if re.search(r':',line):
                m = re.match(r'.*[\(|\s+](.*):(.*):(\d.*)([\'|\"].*)',line)
                if (m):
                    group = m.group(1)
                    artifact = m.group(2)
                    version = m.group(3)    
                    version = re.sub(r'\)','',version)

                    group = re.sub(r'\s+|\'|\"','',group) 
                if (group and version):
                    if (bom_properties.has_key(group) | bom_properties.has_key(group + "." + artifact)):
                        if bom_properties.has_key(group + "." + artifact):
                            good_version = bom_properties[group + "." + artifact]
                        else:
                            good_version = bom_properties[group]
                    
                        if re.match('\$\{.*\}',good_version):
                            good_version = expand_version(good_version, bom_properties)
                        if (not mod_header):
                            mod_logger.info("\n" + lib_file)
                            mod_header = "1"                                            
                        mod_logger.info("\t" + group + ":" + artifact + ":"
                                        + version + " --> " + good_version)                 
                        line = re.sub(re.escape(version), good_version, line)
                    else:
                        if (group and artifact):
                            if (not missing_header):
                                missing_logger.info("\n" + lib_file)
                                missing_header = "1"
                            missing_logger.info("\t" + group + ":" + artifact)

            output.write(line)
            f.close
            output.close
        shutil.move(lib_file + ".mod", lib_file)
        
def find_files(bom_properties):
    filenames = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".gradle"):
                filename = os.path.join(root, file)
                filenames.append(filename)
                
    parse_lib(filenames, bom_properties)                
   
def expand_version(version, bom_properties):
    for k in bom_properties.keys():
        version = re.sub(r'\$|\{|\}|version\.','',version)
        if k == version:
            return bom_properties[k]
        
def _mkdir(newdir):
    """works the way a good mkdir should :)
        - already exists, silently complete
        - regular file in the way, raise an exception
        - parent directory(ies) does not exist, make them as well
    """
    if os.path.isdir(newdir):
        pass
    elif os.path.isfile(newdir):
        raise OSError("a file with the same name as the desired " \
                      "dir, '%s', already exists." % newdir)
    else:
        head, tail = os.path.split(newdir)
        if head and not os.path.isdir(head):
            _mkdir(head)
        #print "_mkdir %s" % repr(newdir)
        if tail:
            os.mkdir(newdir)
        

bom, lib = main()

if (bom.startswith('http')):
    bom = get_bom_from_url(bom)
    
bom_properties = parse_bom(bom)

if lib[0]:
    parse_lib(lib, bom_properties)
else:
    find_files(bom_properties)
