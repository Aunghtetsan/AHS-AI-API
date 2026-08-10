class ConversationLog:
    def __init__(self):
        self.conversations = []

    def add_conversation(self, conversation):
        self.conversations.append(conversation)

    def view_conversations(self):
        for conversation in self.conversations:
            print(conversation)