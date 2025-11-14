#!/usr/bin/env python3
"""
Sample code file for testing the log analyzer.
This simulates a database connection pool service.
"""

class DatabasePool:
    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.active_connections = []
        self.idle_connections = []
        
    def acquire_connection(self):
        """Acquire a database connection from the pool."""
        if self.idle_connections:
            conn = self.idle_connections.pop()
            self.active_connections.append(conn)
            return conn
            
        if len(self.active_connections) < self.max_connections:
            conn = self._create_new_connection()
            self.active_connections.append(conn)
            return conn
            
        # Pool exhausted - this could cause timeouts
        raise Exception("Unable to acquire connection from pool")
    
    def release_connection(self, conn):
        """Release a connection back to the pool."""
        if conn in self.active_connections:
            self.active_connections.remove(conn)
            self.idle_connections.append(conn)
    
    def _create_new_connection(self):
        # Simulate connection creation
        return f"connection_{len(self.active_connections)}"

# User service that might leak connections
class UserService:
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    def get_user_details(self, user_id):
        """Get user details from database."""
        conn = self.db_pool.acquire_connection()
        try:
            # Simulate database query
            result = f"User details for {user_id}"
            return result
        except Exception as e:
            raise e
        # BUG: Missing finally block to release connection!
        # This can cause connection leaks under high load
