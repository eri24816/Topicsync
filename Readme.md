# Chat Room

## Introduction

## Topics

A topic is a variable that is synchronized across all clients. A topic is identified by a string. A topic can be subscribed to by clients. When a topic is updated, all clients subscribed to that topic will receive the update.

The data of a topic can be any JSON-serializable object.

### Special Topics

Special topics starts with `_chatroom/`. They are defined in the ChatRoom library.

* `_chatroom/server_status` - A status string describing the server's nearest event.

* `_chatroom/client_message` - Debug messages (string) to clients. Clients subscribe to `_chatroom/client_message/<id>` to receive debug messages.

## API

All communication is done via a WebSocket connection. Every message has the following format:

```json
{
    "type": "message_type",
    "content": {
        "field1": "value1",
        "field2": "value2",
        ...
    }
}
```

* `type` - The type of message.
* `content` - The actual content of the message.

### Message Types (server -> client)

* `hello` : 

    Fields:

    * id - The id of the client.

* `update` : 

    Fields:

    * topic - The topic that was updated.
    * payload - The payload that was published.

### Message Types (client -> server)

* `publish` : 

    Fields:

    * topic - The topic to publish to.
    * payload - The payload to publish.

* `subscribe` :

    Fields:

    * topic - The topic to subscribe to.

* `unsubscribe` :

    Fields:

    * topic - The topic to unsubscribe from.