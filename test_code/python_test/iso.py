import numpy as np

V = ['A', 'B', 'C', 'D', 'E', 'F']
E = ['AC','AD', 'BD', 'BF', 'CA', 'CF', 'DA', 'DB', 'DF','EF','FB','FC','FD', 'FE']

index = 0
letterToNumberDict = {}
for v in V:
    letterToNumberDict[v] = index
    index += 1

for key, value in letterToNumberDict.items():
    print(key, value)

numVertex = len(V)

graphMatrix = np.zeros((numVertex, numVertex))

for e in range(len(E)):
    v1 = E[e][0]
    v2 = E[e][1]
    graphMatrix[letterToNumberDict[v1], letterToNumberDict[v2]] = 1

def makeDegreeListFromGraphMatrix(graphMatrix):
    degreeList = []
    for i in range(0, len(graphMatrix)):
        degreeList.append(sum(graphMatrix[i]))
    sort = sorted(degreeList)
    return sort

print(makeDegreeListFromGraphMatrix(graphMatrix))

def checkIsomorphism(VA, EA, VB, EB):
    adjMatrixA = listToAdjMatrix(VA, EA)
    degreeListA = makeDegreeListFromGraphMatrix(adjMatrixA)

    adjMatrixB = listToAdjMatrix(VB, EB)
    degreeListB = makeDegreeListFromGraphMatrix(adjMatrixB)

    if degreeListA != degreeListB:
        isoResult = False
    else:
        isoResult = True

    return isoResult

def listToAdjMatrix(V, E):
    index = 0
    letterToNumberDict = {}
    for v in V:
        letterToNumberDict[v] = index
        index += 1

    numVertex = len(V)

    graphMatrix = np.zeros((numVertex, numVertex))

    for e in range(len(E)):
        v1 = E[e][0]
        v2 = E[e][1]
        graphMatrix[letterToNumberDict[v1], letterToNumberDict[v2]] = 1

    return graphMatrix

def main():
    VA = ['A', 'B', 'C', 'D', 'E', 'F']
    EA = ['AC','AD', 'BD', 'BF', 'CA', 'CF', 'DA', 'DB', 'DF','EF','FB','FC','FD', 'FE']
    VB = ['H', 'B', 'J', 'D', 'K', 'F']
    EB = ['HJ','HD', 'BD', 'BF', 'JH', 'JF', 'DH', 'DB', 'DF','KF','FB','FJ','FD', 'FK']
    print(checkIsomorphism(VA, EA, VB, EB))

if __name__ == "__main__":
    main()