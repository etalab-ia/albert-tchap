# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2024-08-10

### 🐛 Bug Fixes

- Prevent conflicting typing await when showing auto-reset message.
- Typo in matrix_bot error log
- Update pyalbert version


## 0.2.0

### 🚀 Features

- Use the chat history to build messages compatible with the openai api [{role, content}].
- Support for reply in thread.
- Improve conversation history management.
- Manage reply in conversation + improved albert messaging.
- Add a minimal system prompt in norag mode
- Improve albert command and response format.
- Add command aliases.
- Add a grist table for user management (implement an minimalistic async grist client)

### 🐛 Bug Fixes

- Pyalbert version for gemma-2 support
- Better error management

### Refacto

- Github actions (#72)
- Bot commands refactorization
- Add all bot custom messages in a dedicated AlbertMsg classe.

### Scripts

- Dump users state list
- Update users table from list
- Send error message demo

