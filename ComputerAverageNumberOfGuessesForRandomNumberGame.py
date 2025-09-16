import random

numberOftries = 0

def computerGuess():
    lowerLimit = 1
    upperLimit = 1000

    correctNumber = random.randint(lowerLimit, upperLimit)

    feedback = ""
    computerGuess = 0
    count = 0

    while(feedback != 'c'):
        
        if lowerLimit == upperLimit:
            computerGuess = lowerLimit
        else:
            computerGuess = random.randint(lowerLimit, upperLimit)

        if computerGuess > correctNumber:
            feedback = 'h'
        elif computerGuess < correctNumber:
            feedback = 'l'
        else:
            feedback = 'c'

        count += 1

        if feedback == 'h':
            upperLimit = computerGuess - 1
        elif feedback == 'l':
            lowerLimit = computerGuess + 1
    
    return count

for x in range (1000):
    numberOftries += computerGuess()
    
print(f"The average number of guess is {numberOftries/ 1000}")