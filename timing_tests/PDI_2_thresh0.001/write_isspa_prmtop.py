
import numpy as np
import sys

##############################################################################################################
#######################################          SUBROUTINES          ########################################
##############################################################################################################

def read_config(cfgFile):
    global prmtopFile, isspaPrmtopFile, isspaMol2File, isspaParamFile, isspaForceFile
    f = open(cfgFile, 'r')
    for line in f:
        # ignore comments
        if '#' in line:
            line, comment = line.split('#',1)
        if '=' in line:
            option, value = line.split('=',1)
            option = option.strip()
            value = value.strip()
            print("Option:", option, " Value:", value)
            # check value
            if option.lower()=='prmtop':
                prmtopFile = value
            elif option.lower()=='isspatop':
                isspaPrmtopFile = value
            elif option.lower()=='isspamol2':
                isspaMol2File = value
            elif option.lower()=='isspadensity':
                isspaParamFile = value
            elif option.lower()=='isspaforce':
                isspaForceFile = value
            else:
                print("Option:", option, " is not recognized")
    f.close()

def read_prmtop(prmtopFile):
    global nAtoms, nRes, residueNumber, residueName, residuePointer
    f = open(prmtopFile, 'r')
    for line in f:
        if '%FLAG POINTERS' in line:
            # skip format line
            line = f.readline()
            line = f.readline()
            data = line.split()
            nAtoms = int(data[0])
            line = f.readline()
            data = line.split()
            nRes = int(data[1])
            residueNumber = np.empty(nAtoms,dtype=int)
            residueLabel = []
            residuePointer = []
        elif '%FLAG RESIDUE_LABEL' in line:
            # skip format line
            line = f.readline()
            # determine number of lines to read
            nLines = int( (nRes+19.0) / 20.0 ) 
            # read lines containing residue labels
            for i in range(nLines):
                line = f.readline()
                data = line.split()
                for elem in data:
                    residueLabel.append(elem)
        elif '%FLAG RESIDUE_POINTER' in line:
            # skip format line
            line = f.readline()
            # determine number of lines to read
            nLines = int( (nRes+9.0) / 10.0 ) 
            # read lines containing residue pointers
            for i in range(nLines):
                line = f.readline()
                data = line.split()
                for elem in data:
                    residuePointer.append(int(elem))

    f.close()
    residueName = []
    resCount = 1
    for i in range(nAtoms):
        if resCount < nRes and i+1 >= residuePointer[resCount]:
            resCount += 1
        residueName.append(residueLabel[resCount-1])
        residueNumber[i] = resCount - 1


def read_mol2(isspaMol2File):
    global resAtomNames, resAtomIsspaType
    f = open(isspaMol2File, 'r')

    for line in f:
        if '@<TRIPOS>MOLECULE' in line:
            line = f.readline()
            resName = line.split()[0]
            line = f.readline()
            resAtoms = int(line.split()[0])
            resAtomNames = []
            resAtomIsspaType = []
        elif '@<TRIPOS>ATOM' in line:
            for i in range(resAtoms):
                line = f.readline()
                data = line.split()
                resAtomNames.append(data[1])
                resAtomIsspaType.append(data[9])
    f.close()

#
def assign_isspa_type(isspaMol2File,residueName,residuePointer):
    nAtoms = len(residueName)
    nRes = len(residuePointer)
    isspaTypes = np.empty(nAtoms,dtype=int)
    read_mol2(isspaMol2File)
    resCount = 1
    resAtomNumber = 0
    for i in range(nAtoms):
        if resCount != nRes and i+1 >= residuePointer[resCount]:
            resCount += 1
            resAtomNumber = 0
        isspaTypes[i] = resAtomIsspaType[resAtomNumber]
        resAtomNumber += 1
    return isspaTypes

def read_isspa_tab_density_file(isspaParamFile):

    tabPoissonRegress = np.loadtxt(isspaParamFile)
    nTypes = int(tabPoissonRegress[-1,2])
    nGRs = tabPoissonRegress.shape[0]//nTypes
    tabGs = np.empty((nGRs,nTypes+1),dtype=float)
    tabCount = 0
    for i in range(1,nTypes+1):
        for j in range(nGRs):
            if (tabPoissonRegress[tabCount,3] <= 0):
                tabGs[j,i] = 0.0
            else:
                tabGs[j,i] = np.exp(tabPoissonRegress[tabCount,1])
            tabCount += 1
    for j in range(nGRs):
        tabGs[j,0] = tabPoissonRegress[j,0]
    return tabGs

def read_isspa_tab_force_file(isspaForceFile):

    forces = np.loadtxt(isspaForceFile)
    return forces

def determine_isspa_domain(isspaGs,isspaForces):
    nForceRs = isspaForces.shape[0]
    nGRs = isspaGs.shape[0]
    nRs = min(nForceRs,nGRs)
    nTypes = isspaForces.shape[1]
    isspaParams = np.empty((nTypes-1,2),dtype=float)
    fg = isspaGs[:nRs,:]*np.abs(isspaForces[:nRs,:])
    thresh = 1E-3
    for i in range(1,nTypes):
        isspaParams[i-1,0] = isspaGs[np.amin(np.argwhere(fg[:,i] > thresh)),0]
        isspaParams[i-1,1] = isspaGs[np.amax(np.argwhere(fg[:,i] > thresh)),0]
    return isspaParams     

def write_isspa_prmtop(isspaPrmtopFile):
    global isspaTypes, nAtoms, isspaParams, isspaForces, isspaGs
    nIsspaTypes = np.amax(isspaTypes)
    nForceRs = isspaForces.shape[0]
    nGRs = isspaGs.shape[0]
    nRs = min(nForceRs,nGRs)
    f = open(isspaPrmtopFile,'w')

    f.write("%VERSION \n")
    f.write("%FLAG TITLE\n")
    f.write("%FORMAT(20a4)\n")
    f.write("PDI\n") # MM
    # Metadata section
    f.write("%FLAG POINTERS\n")
    f.write("%FORMAT(10I8)\n")
    f.write("%8d" % (nAtoms))
    f.write("%8d" % (nIsspaTypes))
    f.write("%8d" % (nRs))
    f.write("%8d" % (nRs))
    f.write("\n")
    # isspa type per atom section
    f.write("%FLAG ISSPA_TYPE_INDEX\n")
    f.write("%FORMAT(10I8)\n")
    for i in range(nAtoms):
        if i>0 and i%10==0:
            f.write("\n")
        f.write("%8d" % (isspaTypes[i]))
    f.write("\n")
    # isspa density parameter section
    f.write("%FLAG ISSPA_MCMIN\n")
    f.write("%FORMAT(5E16.8)\n")
    for i in range(nIsspaTypes):
        if i>0 and i%5==0:
            f.write("\n")
        f.write("%16.8e" % (isspaParams[i,0]))
        #f.write("%16.8e" % (2.5))
    f.write("\n")
    f.write("%FLAG ISSPA_MCMAX\n")
    f.write("%FORMAT(5E16.8)\n")
    for i in range(nIsspaTypes):
        if i>0 and i%5==0:
            f.write("\n")
        f.write("%16.8e" % (isspaParams[i,1]))
        #f.write("%16.8e" % (8.0))
    f.write("\n")
    # isspa tab g(r) section
    f.write("%FLAG ISSPA_DENSITIES\n")
    f.write("%%FORMAT(%dE16.8)\n" %(nIsspaTypes+1))
    for i in range(nRs):
        for j in range(nIsspaTypes+1):
            f.write("%16.8e" % (isspaGs[i,j]))
        f.write("\n")
    # isspa tab force section
    f.write("%FLAG ISSPA_FORCES\n")
    f.write("%%FORMAT(%dE16.8)\n" %(nIsspaTypes+1))
    for i in range(nRs):
        for j in range(nIsspaTypes+1):
            f.write("%16.8e" % (isspaForces[i,j]))
        f.write("\n")
    f.close()

##############################################################################################################
#######################################         MAIN PROGRAM          ########################################
##############################################################################################################


# read in command line argument
cfgFile = sys.argv[1]

# parse config file
read_config(cfgFile)

# parse system prmtop file
read_prmtop(prmtopFile)

# assign isspa types
isspaTypes = assign_isspa_type(isspaMol2File,residueName,residuePointer)
isspaGs = read_isspa_tab_density_file(isspaParamFile)
isspaForces = read_isspa_tab_force_file(isspaForceFile)
isspaParams = determine_isspa_domain(isspaGs,isspaForces)
for i in range(isspaParams.shape[0]):
    print(isspaParams[i,0], isspaParams[i,1])
# write isspa top file
write_isspa_prmtop(isspaPrmtopFile)
