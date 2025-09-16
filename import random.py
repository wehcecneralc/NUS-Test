import random

numberOftries = 0

def computerGuess():
    lowerLimit = 1
    upperLimit = 10

    correctNumber = random.randint(lowerLimit, upperLimit)

    feedback = ""
    computerGuess = 1
    count = 0

    while(feedback != 'c'):
        
        if computerGuess > correctNumber:
            feedback = 'h'
        elif computerGuess < correctNumber:
            feedback = 'l'
        else:
            feedback = 'c'

        count += 1

        if feedback == 'h':
            computerGuess = (computerGuess - lowerLimit)//2+1
            upperLimit = computerGuess
        elif feedback == 'l':
            computerGuess = (upperLimit - computerGuess)//2+1
            lowerLimit = computerGuess

        print(computerGuess)
    return count

computerGuess()
