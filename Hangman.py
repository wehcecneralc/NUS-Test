import random
import string
from HangmanWords import wordArray

def getValidWord():
    word = random.choice(wordArray)

    while '-' in word or ' ' in word:
        word = random.choice(wordArray)

    return word.upper()

def hangman():
    correctWord = getValidWord()
    correctWordList = set(correctWord)
    alphabets = set(string.ascii_uppercase)
    usedAlphabets = set()
    count = 0
    
    while len(correctWordList) > 0:
        print("\n\nYou have used these alphabets: " + ' '.join(usedAlphabets))
        wordList = [letter if letter in usedAlphabets else '_' for letter in correctWord]
        print("Current word: " + " ".join(wordList))

        userInputAlphabet = input("Guess an alphabet: ").upper()
        
        
        if userInputAlphabet in alphabets - usedAlphabets:
            usedAlphabets.add(userInputAlphabet)
            count += 1

            if userInputAlphabet in correctWordList:
                correctWordList.remove(userInputAlphabet)

        elif userInputAlphabet in usedAlphabets:
            print(f"Alphabet {userInputAlphabet} is already used, please try again.")

        else:
            print(f"{userInputAlphabet} is not an alphabet, please try again.")

    print(f"\nCongrats you guessed the word {correctWord} in {count} tries!\n")

hangman()