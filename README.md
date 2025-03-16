# alfred (Work in Progress)
A POC to demonstrate batch-serving of hyper-personalized notifications

# The demo uses: 
1. flask
2. ollama
3. llama3.2:latest model (pulled via ollama)

## to run: 
`python app.py`

The coin toss and dice roll represent a 'new data' event. This occurs every five seconds.

Each user (client) has a textbox connecting them to the central AI. 
Use /notify <coin-toss-outcome> <dice-roll-outcome> to set/update that user's notification preferences
OR enter any other natural langauge query

examples:
1. /notify heads 3
2. /notify_special Only if there have been three consecutive heads.
2. What were the last five coin toss outcomes?
3. How many times has a heads coincided with a dice roll of 3?
