from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import random
import time
from threading import Thread
from ollama import Client
import queue

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize Ollama client
ollama_client = Client(host='http://localhost:11434')

# Global state and history
current_state = {"coin": None, "dice": None}
state_history = []  # Full history
users = [
    {"name": "Alice", "condition": "", "special_condition": "", "count": 0},
    {"name": "Bob", "condition": "", "special_condition": "", "count": 0},
    {"name": "Charlie", "condition": "", "special_condition": "", "count": 0},
    {"name": "David", "condition": "", "special_condition": "", "count": 0},
    {"name": "Eve", "condition": "", "special_condition": "", "count": 0}
]
pending_notifications = []  # To batch notifications
state_queue = queue.Queue()  # Queue to pass states to condition checker

@app.route('/')
def index():
    return render_template('index.html', users=users)

@socketio.on('update_condition')
def handle_condition_update(data):
    index = data['index']
    input_text = data['condition'].strip()

    if input_text.lower().startswith('/notify_special'):
        special_condition = input_text[len('/notify_special'):].strip()
        users[index]['special_condition'] = special_condition if special_condition else ""
        emit('update_users', users, broadcast=True)
    elif input_text.lower().startswith('/notify'):
        condition = input_text[len('/notify'):].strip().lower()
        users[index]['condition'] = condition if condition else ""
        emit('update_users', users, broadcast=True)
    else:
        response = process_question(input_text)
        emit('notification', {
            'index': index,
            'message': response
        })

def process_question(question):
    history_context = "Here’s the history of coin tosses and dice rolls (up to the last 20 entries):\n"
    for entry in state_history[-20:]:
        history_context += f"At {time.ctime(entry['timestamp'])}: Coin={entry['coin']}, Dice={entry['dice']}\n"
    prompt = f"{history_context}\nUser question: {question}\nAnswer concisely based on the history:"
    response = ollama_client.generate(model='llama3.2', prompt=prompt)
    return response['response'].strip()

def evaluate_special_conditions(users, state_history):
    """Batch evaluate all users' special conditions with one LLaMA call."""
    if not state_history or not any(user['special_condition'] for user in users):
        return []

    # Build prompt with all users' conditions
    history_context = "Here’s the history of coin tosses and dice rolls (up to the last 20 entries):\n"
    for entry in state_history[-20:]:
        history_context += f"At {time.ctime(entry['timestamp'])}: Coin={entry['coin']}, Dice={entry['dice']}\n"
    
    conditions_text = "User notification preferences / condition:\n"
    for i, user in enumerate(users):
        if user['special_condition']:
            conditions_text += f"User {i}: {user['special_condition']}\n"
    
    prompt = (
        f"{history_context}\n"
        f"{conditions_text}\n"
        f"For which users does the history satisfy the condition for which they want to be notified? "
        f"Return a list of user indices (e.g., [0, 2, 4]) or [] if none."
    )
    
    response = ollama_client.generate(model='llama3.2', prompt=prompt)
    print(f"Raw response from LLM: {response}")
    try:
        # Parse response as a list of indices (e.g., "[0, 2]" -> [0, 2])
        indices = eval(response['response'].strip())
        print(f"Indices returned by LLM: {indices}")
        if isinstance(indices, list) and all(isinstance(i, int) and 0 <= i < len(users) for i in indices):
            print(f"These are the returned indices by the LLM: {indices}")
            return indices
        return indices
    except (SyntaxError, ValueError, TypeError):
        return []  # Fallback if response isn’t a valid list

def notification_loop():
    """Emit batched notifications every 10 seconds."""
    while True:
        time.sleep(10)
        if pending_notifications:
            for notification in pending_notifications:
                socketio.emit('notification', notification)
            pending_notifications.clear()
            socketio.emit('status_update', {'message': 'Notifications dispatched!'})

def game_loop():
    """Generate coin tosses and dice rolls every 1 second."""
    while True:
        current_state['coin'] = random.choice(['heads', 'tails'])
        current_state['dice'] = random.randint(1, 6)
        timestamp = time.time()
        
        state_entry = {
            'coin': current_state['coin'],
            'dice': current_state['dice'],
            'timestamp': timestamp
        }
        state_history.append(state_entry)
        state_queue.put(state_entry)
        
        socketio.emit('game_update', current_state)
        socketio.emit('update_users', users)
        
        time.sleep(1)

def condition_check_loop():
    """Check conditions asynchronously using queued states."""
    while True:
        try:
            state_entry = state_queue.get(timeout=0.1)
            current_event = f"{state_entry['coin']} {state_entry['dice']}"
            timestamp = state_entry['timestamp']
            
            # Check /notify conditions (simple string match)
            for index, user in enumerate(users):
                if user['condition'] and user['condition'] == current_event:
                    user['count'] += 1
                    pending_notifications.append({
                        'index': index,
                        'condition': user['condition'],
                        'event': current_event,
                        'timestamp': time.ctime(timestamp)
                    })
            
            # Batch check /notify_special conditions with one LLM call
            triggered_indices = evaluate_special_conditions(users, state_history)
            for index in triggered_indices:
                user = users[index]
                user['count'] += 1
                pending_notifications.append({
                    'index': index,
                    'condition': user['special_condition'],
                    'event': current_event,
                    'timestamp': time.ctime(timestamp)
                })
            
            state_queue.task_done()
        except queue.Empty:
            time.sleep(0.1)

if __name__ == '__main__':
    Thread(target=game_loop, daemon=True).start()
    Thread(target=condition_check_loop, daemon=True).start()
    Thread(target=notification_loop, daemon=True).start()
    socketio.run(app, debug=True)