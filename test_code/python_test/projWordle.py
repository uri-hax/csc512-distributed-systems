
# Program Title: Wordle Implementation

# Program Description: 
# ---------------------
# This program will generate a random 5 letter word and then the player will make guesses based on clues provided by the program.
# The program will keep track of the score and provide clues to the user.


import random


# This function will open the file and check the given file name
def openFile():
    goodFile = False
    while goodFile == False:
        fname = input("Please enter a file name: ")
        try:
            dataFile = open(fname, "r")
            goodFile = True
        except IOError:
            print("Invalid file name try again ...")
    return dataFile

# Function to read in the data from the file
def getData ():
    inFile = openFile()
    wordList = []
    # Skip the header line
    headers = next(inFile)
    for line in inFile:
        line = line.strip()
        word = line
        wordList.append(word)
    
    inFile.close()
    return wordList

# Function to generate a random 5 letter word
def generateWord(wordList):
    # Pulls a random word from the list
    wordIndex = random.randint(0, len(wordList) - 1)
    # Returns the word at the index (-1 to match the list index)
    word = wordList[wordIndex - 1]
    return word

# Function to get the user's guess
def getGuess(wordList, guessList):
    while True:
        guess = input("Make a guess: ").upper()
        if guess not in wordList:
            print('Word not in dictionary - try again... ')
        elif guess in guessList:
            print("You have already guessed that word, try again ...")
        else:
            return guess

# Function to compute the clue based on the user's guess
def computeClue(guess, word):
    clue = ""
    # Empty list to keep track of the location of the correctly guessed letters in the word
    matched_letters = [] 
    for i in range(len(word)):
        if guess[i] == word[i]:
            clue += 'G'
            matched_letters.append(i)
        # Checks if the letter is in the word but not in the correct location
        # Then checks if the letter has already been placed correctly in another spot using the matched_letters list
        elif guess[i] in word and word.index(guess[i]) not in matched_letters:
            # Accounts for double letters and returns 'X' if the letter has already been placed correctly in another spot
            if guess.count(guess[i]) > word.count(guess[i]):
                clue += 'X'
            else:
                clue += 'Y'
            matched_letters.append(word.index(guess[i]))
        else:
            clue += 'X'
    return clue

def main(seedIn):
    # Initialize variables
    gameScore = 0
    random.seed(seedIn)

    # Generate a list of words
    wordList = getData()
    # Keeps track of the game vs the round
    playAgain = 'Y'

    # Game loop to ensure the player can play multiple rounds
    while playAgain.upper() == 'Y':
        word = generateWord(wordList)
        guessList = []
        guessCount = 1
        roundScore = 1

        guess = getGuess(wordList, guessList)

        # Loop to keep track of the guesses and provide clues
        while guess != word and guessCount < 6:
            guessList.append(guess)
            # Increment score for each guess
            guessCount += 1
            roundScore += 1
            clue = computeClue(guess, word)
            print(guess)
            print(clue)
            guess = getGuess(wordList, guessList)
        
        # Condition if the word is guessed correctly
        if guess == word:
            clue = computeClue(guess, word)
            print(guess)
            print(clue)
            print()
            print('Congratulations, your wordle score for this game is ', roundScore)
            # Increment the overall score
            gameScore += roundScore
            print('Your overall score is ', gameScore)
            print()
        # Condition if the word is not guessed correctly in 6 guesses
        else:
            print(guess)
            clue = computeClue(guess, word)
            print(clue)
            print("Sorry, you did not guess the word: ", word)
            roundScore = 10
            gameScore += roundScore
            print('Your overall score is ', gameScore)
            print()

        # Either end the while loop and end the game or reset the game while gameScore continues to increment 
        playAgain = input('Would you like to play again (Y or N)? ')

    print('Thanks for playing!')

# main(2)