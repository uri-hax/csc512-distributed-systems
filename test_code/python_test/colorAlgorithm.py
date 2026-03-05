import numpy as np
from itertools import permutations 
from itertools import product
def FindMinColor(graphMatrix):
    #Get the number of vertices 
    numVertex = graphMatrix.shape[0]
    #In the worst case each node needs its own color
    minNumColors = numVertex
    #Try from a 1 coloring all the way up to a numVertex-1 coloring
    for colorNum in range(1, numVertex):
        #Create a list with all the possible colors as integers
        colorList = list(range(0, colorNum))
        print("ColorNum=", colorNum)
        print("Color List=", colorList)
        #Create all the possible permutations from the given color list
        allPermutationsForColorNum =  product(colorList, repeat = numVertex)
        #Go through each permutation and check if satisfies the coloring conditions 
        for coloringSolution in list(allPermutationsForColorNum):
            isValidSolution = CheckColoringSolution(list(coloringSolution), graphMatrix)
            if isValidSolution == True:
                minNumColors = colorNum
                #No need to continue, we found the solution
                return minNumColors
    return minNumColors


def CheckColoringSolution(coloringSolution, graphMatrix):
    #Given the coloringSolution and graphMatrix as a 2D numpy array,
    #check if the coloring solution is valid.
    #Return true if it is a valid coloring solution, false otherwise
    numVertex = len(coloringSolution)
    for i in range(numVertex):
        for j in range(numVertex):
            if graphMatrix[i,j] == 1 and coloringSolution[i] == coloringSolution[j]:
                return False
    return True


# graphMatrix = np.zeros((4,4))
# graphMatrix[0,1] = 1 
# graphMatrix[0,2] = 1 
# graphMatrix[1,0] = 1 
# graphMatrix[1,3] = 1 
# graphMatrix[2,0] = 1 
# graphMatrix[2,3] = 1 
# graphMatrix[3,1] = 1 
# graphMatrix[3,2] = 1
# graphMatrix[0,3] = 1
# graphMatrix[3,0] = 1

graphMatrix = np.zeros((8, 8))

# Connect nodes in a ring
for i in range(8):
    graphMatrix[i, (i + 1) % 8] = 1  # Connect to the next node (cyclically)
    graphMatrix[(i + 1) % 8, i] = 1  # Connect back to the previous node (undirected)


print(FindMinColor(graphMatrix))