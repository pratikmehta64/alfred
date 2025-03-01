from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread
from ollama import Client

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize Ollama client (assuming LLaMA 3.2 is running locally via Ollama)
ollama_client = Client(host='http://localhost:11434')  # Default Ollama host

# Global state and history
current_state = {"coin": None, "dice": None}
state_history = []  # List to store past states: [{"coin": "heads", "dice": 3, "timestamp": timestamp}, ...]
users = [
    {"name": "Alice", "condition": "", "count": 0},
    {"name": "Bob", "condition": "", "count": 0},
    {"name": "Charlie", "condition": "", "count": 0},
    {"name": "David", "condition": "", "count": 0},
    {"name": "Eve", "condition": "", "count": 0}
]

@app.route('/')
def index():
    return render_template('index.html', users=users)

@socketio.on('update_condition')
def handle_condition_update(data):
    index = data['index']
    input_text = data['condition'].strip().lower()

    if input_text.startswith('/notify'):
        # Handle notification condition
        condition = input_text[len('/notify'):].strip()
        users[index]['condition'] = condition if condition else ""
        emit('update_users', users, broadcast=True)
    else:
        # Handle natural language question
        response = process_question(input_text)
        emit('notification', {
            'index': index,
            'message': response
        })

def process_question(question):
    # Prepare context from state history
    history_context = "Here’s the history of coin tosses and dice rolls:\n"
    for entry in state_history[-10:]:  # Limit to last 10 for brevity
        history_context += f"At {time.ctime(entry['timestamp'])}: Coin={entry['coin']}, Dice={entry['dice']}\n"
    
    # Query LLaMA 3.2 via Ollama
    prompt = f"{history_context}\nUser question: {question}\nAnswer concisely based on the history:"
    response = ollama_client.generate(model='llama3.2', prompt=prompt)
    return response['response'].strip()

def game_loop():
    while True:
        # Simulate coin toss and dice roll
        current_state['coin'] = random.choice(['heads', 'tails'])
        current_state['dice'] = random.randint(1, 6)
        
        # Store in history with timestamp
        state_history.append({
            'coin': current_state['coin'],
            'dice': current_state['dice'],
            'timestamp': time.time()
        })
        
        # Check user conditions
        current_event = f"{current_state['coin']} {current_state['dice']}"
        for index, user in enumerate(users):
            if user['condition'] and user['condition'] == current_event:
                user['count'] += 1
                socketio.emit('notification', {
                    'index': index,
                    'condition': user['condition'],
                    'event': current_event
                })
        
        # Broadcast updates
        socketio.emit('game_update', current_state)
        socketio.emit('update_users', users)
        
        time.sleep(5)

if __name__ == '__main__':
    Thread(target=game_loop, daemon=True).start()
    socketio.run(app, debug=True)