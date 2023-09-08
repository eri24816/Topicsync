# ChatRoom
 
## TODOs

## Introduction

ChatRoom is a communication tool for multi-client applications where clients' states need to be syncronized in real-time, such as real-time collaborative tools or multiplayer games. ChatRoom provides a **topic system** and a **service system**. The topic system manages Topic. Each `Topic` has its value that is avaliable to all clients that subscribes to it and is changable from every client.

## Topics

A topic stores a piece of data that is synchronized across clients. Clients can subscribe to topics and update topics. When one client makes a change on a topic's value, all clients subscribed to that topic will receive the change.

### Special Topics

Special topics are those with their names begin with `_chatroom/`.

* `_chatroom/server_status` 

    A status string describing the server's nearest event.
* `_chatroom/client_message/<client_id>` 
    
    Debug messages (string) to clients. Clients subscribe to it to receive debug messages.

## Services

Using a service, a client can call a function in another client and get the return value.

### Special Services

Special services are those with their names begin with `_chatroom/`.

## Debugging

Set DEBUG environment variable to `true` to enable debug mode. Debugger listens on http://localhost:8800.

## Internal Communication API (Outdated, need to be updated later)

The communication between a ChatRoom server and a client is done via a WebSocket connection. Every message has the following format:

```json
{
    "type": "<message_type>",
    "content": {
        "<field1>": "<value1>",
        "<field2>": "<value2>",
        ...
    }
}
```

Where `type` is the type of message and `content` is the actual content of the message. For each message type, there are specified fields that should be in the `content`.

These are all message types used in ChatRoom:

### Message Types (server -> client)

#### hello

- id : The given id of the client.

#### update

- topic_name : The topic that was updated.
- change : A dictionary that contains the serialized information of the `Change` object.

#### reject_update

- topic_name : The topic that was rejected.
- change : The change that was rejected.
- reason : A string describing why the update is rejected.

#### request

- service_name : The service to call.
- args : The argument to pass to the service.
- request_id : A unique id of the request.

#### response

- response : The response content.
- request_id : The same id as in the request message.

### Message Types (client -> server)

#### request

- service_name : The service to call.
- args : The argument to pass to the service.
- request_id : A unique id of the request.

#### response

- response : The response content.
- request_id : The same id as in the request message.

#### register_service

- service_name : The name of the registered service.

#### unregister_service

- service_name : The name of the unregistered service.

#### subscribe

- topic_name : The subscribed topic.
- type : In case of the subcribed topic has not exist, the server will initialize the topic with this type.

#### unsubscribe

- topic_name : The unsubscribed topic.

#### update

- topic_name : The updated topic.
- change : A dictionary that contains the serialized information of the `Change` object.