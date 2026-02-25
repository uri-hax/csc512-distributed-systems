package main

import (
	"fmt"
	"math/rand"
	"sync"
	"time"
)

// mutex for synchronizing access to ballotBox
var mutex sync.Mutex
var ballotBox = make(map[string]int)

func resetBallotBox(words []string) {
	mutex.Lock()
	defer mutex.Unlock()
	for _, word := range words {
		ballotBox[word] = 0
	}
}

func castVote(word string, waitGroup *sync.WaitGroup) {
	defer waitGroup.Done()
	mutex.Lock()
	ballotBox[word]++
	mutex.Unlock()
}

func getWinner(words []string) (string, int, bool) {
	mutex.Lock()
	defer mutex.Unlock()

	maxVotes := 0
	winner := "None"
	tied := false

	for _, word := range words {
		fmt.Println(word, ballotBox[word])
		if ballotBox[word] > maxVotes {
			maxVotes = ballotBox[word]
			winner = word
			tied = false
		} else if ballotBox[word] == maxVotes {
			tied = true
		}
	}
	return winner, maxVotes, tied
}

func main() {
	rand.New(rand.NewSource(time.Now().UnixNano()))

	text := []string{"Hi", "My", "Name", "Is", "Hello"}
	var waitGroup sync.WaitGroup

	voting := true

	for voting {
		resetBallotBox(text)

		for range 10 {
			waitGroup.Add(1)
			index := rand.Intn(len(text))
			go castVote(text[index], &waitGroup)
		}

		waitGroup.Wait()
		winner, max, tied := getWinner(text)

		if tied {
			fmt.Println("There was a tie, redoing vote.")
		} else {
			voting = false
			fmt.Println("The winner is", winner, "with", max, "votes.")
		}
	}
}
