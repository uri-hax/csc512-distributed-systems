#Make the vertex class
class Vertex():
    def __init__(self, name, neighborList=None, isVisited=False):
        self.name = name
        self.neighborList = neighborList
        self.isVisited = isVisited
#Create the vertices
A = Vertex("A")
B = Vertex("B")
C = Vertex("C")
D = Vertex("D")
E = Vertex("E")
F = Vertex("F")
G = Vertex("G")
H = Vertex("H")
I = Vertex("I")

A.neighborList=[B, D]
B.neighborList=[A, C]
C.neighborList=[B, D, F]
D.neighborList=[C, E]
E.neighborList=[A, D]
F.neighborList=[C]
H.neighborList=[G, I]
I.neighborList=[H, G]
G.neighborList=[H, I]

Graph = {"A":A, "B":B, "C":C, "D":D, "E":E, "F":F,"G":G,"H":H,"I":I}


def dfs(Graph, inputVertexName, count):
    #Mark the inputVertex as visited
    #Update the count variable
    #Go through all neighbors of the inputVertex
    inputVertex = Graph[inputVertexName]
    inputVertex.isVisited = True
    count += 1

    for v in Graph[inputVertexName].neighborList:
        #Check if v has been visited yet, if not call dfs on v
        if not v.isVisited:
            count = dfs(Graph, v.name, count)
    return count 

def CheckForConnectedGraph(Graph, inputVertexName, numNodes):
    #set the count variable to 0
    count = 0
    count = dfs(Graph, inputVertexName, count)
    #check if count matches the numNodes
    if count == numNodes:
        return True
    else:
        return False
    #Return true if graph is connected, otherwise return false

#An example function call 
numNodes = 9
print(CheckForConnectedGraph(Graph, "A", numNodes))

#--------------------------------------------

A = Vertex("A")
B = Vertex("B")
C = Vertex("C")
D = Vertex("D")
A.neighborList=[B, C, D]
B.neighborList=[A, C, D]
C.neighborList=[A, B, D]
D.neighborList=[A, B, C]
Graph = {"A":A, "B":B, "C":C, "D":D}


#function to test for completeness
def TestForCompleteness(Graph, numNeighbors):
    for vertex in Graph:
        if len(Graph[vertex].neighborList) != numNeighbors:
            return False
    return True

#An example function call
numNeighbors = 3
print(TestForCompleteness(Graph, numNeighbors))


