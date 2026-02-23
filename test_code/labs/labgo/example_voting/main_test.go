package main

import (
	"sync"
	"testing"
)

// test resetting the ballot box
func TestResetBallotBox(t *testing.T) {
	words := []string{"A", "B", "C", "D", "E", "F", "A", "B", "C", "D", "E", "F"}
	resetBallotBox(words)

	mutex.Lock()
	defer mutex.Unlock()

	for _, word := range words {
		if ballotBox[word] != 0 {
			t.Errorf("Expected %s to have 0 votes, got %d", word, ballotBox[word])
		}
	}
}

// test single vote counting
func TestCastVote(t *testing.T) {
	words := []string{"A", "B", "C"}
	resetBallotBox(words)

	var waitGroup sync.WaitGroup
	waitGroup.Add(1)
	castVote("A", &waitGroup)
	waitGroup.Wait()

	mutex.Lock()
	defer mutex.Unlock()

	if ballotBox["A"] != 1 {
		t.Errorf("Expected A to have 1 vote, got %d", ballotBox["A"])
	}
}

// test concurrent voting with multiple goroutines
func TestConcurrentVoting(t *testing.T) {
	words := []string{"A", "B", "C"}
	resetBallotBox(words)

	var waitGroup sync.WaitGroup
	numVotes := 100

	for i := 0; i < numVotes; i++ {
		waitGroup.Add(1)
		go castVote("B", &waitGroup)
	}
	waitGroup.Wait()

	mutex.Lock()
	defer mutex.Unlock()

	if ballotBox["B"] != numVotes {
		t.Errorf("Expected B to have %d votes, got %d", numVotes, ballotBox["B"])
	}
}

// test winner selection
func TestGetWinner(t *testing.T) {
	words := []string{"A", "B", "C"}
	resetBallotBox(words)

	mutex.Lock()
	ballotBox["A"] = 3
	ballotBox["B"] = 5
	ballotBox["C"] = 2
	mutex.Unlock()

	winner, votes, tied := getWinner(words)

	if winner != "B" || votes != 5 || tied {
		t.Errorf("Expected winner B with 5 votes, got %s with %d votes (tie: %v)", winner, votes, tied)
	}
}

// test tie detection
func TestTieDetection(t *testing.T) {
	words := []string{"A", "B"}
	resetBallotBox(words)

	mutex.Lock()
	ballotBox["A"] = 4
	ballotBox["B"] = 4
	mutex.Unlock()

	winner, votes, tied := getWinner(words)

	if !tied {
		t.Errorf("Expected a tie, but got winner %s with %d votes", winner, votes)
	}
}
