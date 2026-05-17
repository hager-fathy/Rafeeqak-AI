# Databases Demo Notes

## Transactions

A database transaction is a group of operations that should succeed or fail as one unit. Transactions protect data consistency when several operations depend on each other.

The ACID properties are:

- Atomicity: all operations happen, or none of them happen.
- Consistency: the database moves from one valid state to another valid state.
- Isolation: concurrent transactions should not corrupt each other.
- Durability: committed changes survive failures.

## Indexes

An index is a data structure that helps the database find rows faster. Indexes are useful for frequent search, join, and filtering columns. However, indexes can slow down inserts and updates because the database must maintain the index after data changes.

Good index decisions depend on query patterns, selectivity, and the cost of maintaining extra structures.

