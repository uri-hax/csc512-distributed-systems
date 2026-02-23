import itertools

class Doc():
   def __init__(self, docName, numSentences, wordsPerSentence):
        self.docName = docName
        self.numSentences = numSentences
        self.wordsPerSentence = wordsPerSentence

docNames = ["doc1","doc2","doc3","doc4","doc5","doc6","doc7"]
sentencePerDocList =[72, 52, 75, 40, 61, 55, 68]
wordPerSentenceList = [13, 20, 22, 28, 25, 19, 17]
allDocsObjectList = []
#Fill in the document class
for i in range(0, len(docNames)):
    allDocsObjectList.append(Doc(docNames[i],sentencePerDocList[i],wordPerSentenceList[i]))

def ComputeTrainingCombinations(allDocsObjectList):
    r = 3
    allRCombinationsList = []
    for subset in itertools.combinations(allDocsObjectList, r):
        allRCombinationsList.append(list(subset))
    return allRCombinationsList

allRCombinationsList = ComputeTrainingCombinations(allDocsObjectList)

def ComputeTrainingSamples(allRCombinationsList):
    trainingSamplesList = []
    for i in range(0, len(allRCombinationsList)):
        numTrainingSamples = 1
        for x in allRCombinationsList[i]:
            numTrainingSamples *= x.numSentences
        trainingSamplesList.append(numTrainingSamples)
    return trainingSamplesList

trainingSamplesList = ComputeTrainingSamples(allRCombinationsList)
 
def BestCombination(allRCombinationsList, trainingSamplesList):
    bestCombination = allRCombinationsList[0]
    bestTrainingSamples = trainingSamplesList[0]
    for i in range(1, len(trainingSamplesList)):
        if trainingSamplesList[i] > bestTrainingSamples:
            bestTrainingSamples = trainingSamplesList[i]
            bestCombination = allRCombinationsList[i]
    return bestCombination, bestTrainingSamples

bestCombination, bestTrainingSamples = BestCombination(allRCombinationsList, trainingSamplesList)
for x in bestCombination: print(x.docName)
print(bestTrainingSamples)
print("=========")
