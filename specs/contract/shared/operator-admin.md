---
type: contract
name: Operator admin
context:
  - src/shared/presentation/admin.py
  - src/main.py
created: 2026-09-28
---

## Purpose

A browser page under `/admin` where an operator of this server looks at, and changes by hand, the
records it holds — the way Django's admin does — without writing requests to the API. It is an
operator's tool, guarded by its own credentials, never a client surface. Which records it shows is
added context by context; this spec covers the door, not the rooms.

## Behaviors

### The admin is closed until an operator has signed in

- **Given** a visitor with no admin session
- **When** it opens any page under `/admin`
- **Then** it is sent to the admin's sign-in page, and no record is shown to it
- **Why** the admin changes every row the API guards; open, it would hand the whole store to
  anyone who can reach the port.

### An operator signs in with the admin credentials

- **Given** the server was started with an admin username and password configured
- **When** a visitor signs in with exactly that username and that password
- **Then** it is let in and stays signed in for its browser session, until it signs out
- **And** the session cookie has no expiry of its own, and outside local development it is sent
  over HTTPS only
- **Why** a cookie that outlives the browser, or travels in clear text, is a sign-in anyone who
  copies it keeps.

### Wrong credentials are refused

- **Given** the sign-in page
- **When** a visitor signs in with a wrong username, a wrong password, or either left empty
- **Then** it stays on the sign-in page, signed out, and learns nothing about which of the two was
  wrong

### The API key is not an admin credential

- **Given** a visitor that knows the API key clients use
- **When** it signs in to the admin with that key as the password
- **Then** it is refused, unless the operator chose the same value for both
- **Why** the key is handed to every client; the admin is for whoever runs the server.

### Without a configured password there is no admin at all

- **Given** the server was started with no admin password, or no admin session secret
- **When** anyone opens `/admin`
- **Then** the answer is `404`, exactly as for any path the server does not serve
- **Why** a default password that ships with the code is a password everybody knows; an admin that
  does not exist cannot be signed in to.

### A sign-in expires on the server

- **Given** an operator signed in more than 12 hours ago, still holding its session cookie
- **When** it opens any page under `/admin`
- **Then** it is sent to the sign-in page again
- **Why** the cookie is signed, not stored: signing out clears it only in one browser, so a copied
  cookie would otherwise open the admin until the session secret is changed.

### Signing out ends the session at once

- **Given** a signed-in operator
- **When** it signs out
- **Then** the next page under `/admin` asks it to sign in again

## Invariants

- No admin page, including the sign-in page's errors, ever shows the API key or a credential a
  record carries.
- The API's own behavior does not change because the admin exists: every API route keeps its key.

## Failure Modes

- **Not signed in** — sent to the sign-in page; nothing is shown and nothing changes.
- **The database is unreachable** — the page fails; nothing is half-written.

## Edge Cases

- Signing in twice in a row keeps one session; signing out after that ends it.

## Out of Scope

- The views of each context's records — each context specs its own.
- More than one operator account, operator roles, or per-model permissions.
- An audit trail of what an operator changed.
- Rate limiting or locking out repeated failed sign-ins.
