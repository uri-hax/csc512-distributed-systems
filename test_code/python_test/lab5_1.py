#Take in a list of sentances (strings)
#Return all possible training input/output pairs for each sentance
#Return the total number of training/output pairs and the number of words

def LLMDataCounter(sentanceList):
    wordCount = 0
    trainingData = []
    for i in range (0, len(sentanceList)):
        words = sentanceList[i].split()
        wordCount += len(words)
        for j in range(1, len(words)):
            input = ' '.join(words[:j])
            trainingData.append(input)
    numTrainingSamples = len(trainingData)
    return trainingData, numTrainingSamples, wordCount

sentanceList = ["Hello how are you", "What is up"]
trainingData, numTrainingSamples, wordCount = LLMDataCounter(sentanceList)
print("wordCount = ", wordCount)
print("numTrainingSamples = ", numTrainingSamples)
print("trainingData = ", trainingData)

