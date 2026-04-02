# API Specification

## Overview
This project provides three API groups:
- Auth: register, login, profile, change password
- Document Registry: upload document and list uploaded documents
- Chat: ask questions with conversation history

Knowledge base behavior is simplified:
- The system only records what documents were uploaded.
- No extra upload parameters are required.
- Document records are isolated per account.

## Auth APIs
Base path: `/api/auth`

### POST `/register`
Request (JSON):
```json
{
  "username": "demo_user",
  "email": "demo@example.com",
  "password": "12345678"
}
```
Response:
```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "username": "demo_user",
  "message": "..."
}
```

### POST `/login`
Request (JSON):
```json
{
  "username": "demo_user",
  "password": "12345678"
}
```
Response is the same shape as register.

### GET `/profile`
Header:
- `Authorization: Bearer <token>`

Response:
```json
{
  "id": 1,
  "username": "demo_user",
  "email": "demo@example.com",
  "message": "..."
}
```

### POST `/change-password`
Request (JSON):
```json
{
  "username": "demo_user",
  "old_password": "12345678",
  "new_password": "87654321",
  "confirm_password": "87654321"
}
```
Response:
```json
{
  "message": "..."
}
```

## Document Registry APIs
Base path: `/api/vector-store`

All endpoints in this section require:
- `Authorization: Bearer <token>`

### POST `/upload`
Content-Type: `multipart/form-data`
Form field:
- `file`
Supported file extensions:
- `.pdf`
- `.txt`
- `.md`
- `.html`
- `.htm`
- `.csv`
- `.json`
- `.jsonl`

Response:
```json
{
  "filename": "demo.txt",
  "message": "Document uploaded successfully and recorded."
}
```

### GET `/documents`
Response:
```json
[
  {
    "id": 1,
    "filename": "demo.txt",
    "status": "recorded"
  }
]
```

## Chat APIs
Base path: `/api/chat`

### POST `/completion`
Request (JSON):
```json
{
  "question": "What is in my uploaded documents?",
  "top_k": 5,
  "history": []
}
```

Notes:
- `top_k` defaults to `5`
- current online retrieval pipeline is `hybrid recall -> weighted RRF -> MMR compression`
- request range for `top_k` is `1..20`

Response:
```json
{
  "answer": "...",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```
