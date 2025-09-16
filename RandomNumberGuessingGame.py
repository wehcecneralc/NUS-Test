import random

guess = 0
count = 0

def randomNumberUpperLimit(x):
    randomNumber = random.randint(1, x)
    return randomNumber

upperLimit = int(input("Guess a number from 1 to __ \nSet the upper limit: "))
randomNumber = randomNumberUpperLimit(upperLimit)

print("Game has started!")

while (guess != randomNumber):
    guess = int(input("Guess a number: "))
    count += 1

    if(guess == randomNumber):
        print(f"Congrats, you've guessed the number in {count} tries!")
    elif(guess < randomNumber):
        print("Guess a higher number")
    elif(guess > randomNumber):
        print("Guess a lower number")