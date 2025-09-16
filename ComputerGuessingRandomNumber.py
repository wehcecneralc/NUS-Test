import random

def computerGuess():
    lowerLimit = 1
    upperLimit = 1000

    feedback = ""
    computerGuess = 0
    count = 0

    print("\nI am going to guess a number that you are thinking of from 1 to 1000\n")

    while(feedback != 'c'):
        
        if lowerLimit == upperLimit:
            computerGuess = lowerLimit
        else:
            computerGuess = (upperLimit + lowerLimit)//2

        feedback = input(f"Is the number {computerGuess} too high(h), too low(l), or correct(c)? \n")
        count += 1

        if feedback == 'h':
            upperLimit = computerGuess - 1
        elif feedback == 'l':
            lowerLimit = computerGuess + 1
        else:
            print("Error")
    
    print(f"I guessed your number {computerGuess} correctly in {count} tries!")

computerGuess()