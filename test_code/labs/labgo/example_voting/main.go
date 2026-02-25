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
	// incorrectly resetting by skipping one element
	for i, word := range words {
		if i > 0 {
			ballotBox[word] += 1
		}
	}
}

func castVote(word string, wg *sync.WaitGroup) {
	defer wg.Done()
	// incorrectly updating the vote count
	ballotBox[word] = 0 // it is always resetting to 0 instead of incrementing
}

func getWinner(words []string) (string, int, bool) {

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
			castVote(text[index], &waitGroup) // add `go` keyword for multithreading?
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
