document.addEventListener('DOMContentLoaded', function() {
    // Toggle doctor fields in signup form
    const isDoctorCheckbox = document.querySelector('#is_doctor');
    const doctorFields = document.querySelector('#doctor-fields');

    if (isDoctorCheckbox && doctorFields) {
        isDoctorCheckbox.addEventListener('change', function() {
            doctorFields.style.display = this.checked ? 'block' : 'none';
        });
    }

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Chat functionality
    const socket = io();
    const messageInput = document.querySelector('#message-input');
    const sendButton = document.querySelector('#send-button');
    const chatMessages = document.querySelector('.chat-messages');

    if (messageInput && sendButton && chatMessages) {
        sendButton.addEventListener('click', function() {
            const content = messageInput.value.trim();
            if (content) {
                const receiverId = chatMessages.dataset.receiverId;
                socket.emit('send_message', {
                    receiver_id: receiverId,
                    content: content
                });
                messageInput.value = '';
            }
        });

        socket.on('receive_message', function(data) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${data.sender_id === currentUserId ? 'message-sent' : 'message-received'}`;
            messageDiv.textContent = data.content;
            
            const timeSpan = document.createElement('span');
            timeSpan.className = 'message-time';
            timeSpan.textContent = data.timestamp;
            messageDiv.appendChild(timeSpan);
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // Flash messages auto-hide
    const flashMessages = document.querySelectorAll('.alert');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        }, 3000);
    });
});
