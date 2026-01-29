"""ZeroMQ message router - subscribes to Lua PUB socket and routes messages to handlers."""

import asyncio
import json
from typing import Any, Callable, Awaitable

import zmq
import zmq.asyncio
from loguru import logger


# Type alias for handler functions
MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class ZMQRouter:
    """Routes ZMQ messages to registered handlers based on topic.
    
    Connects to Lua's PUB socket and subscribes to all topics.
    Messages are expected in format: "<topic> <json-payload>"
    """
    
    def __init__(self, endpoint: str):
        """Initialize router.
        
        Args:
            endpoint: ZMQ endpoint to connect to (e.g., "tcp://127.0.0.1:5555")
        """
        self.endpoint = endpoint
        self.handlers: dict[str, MessageHandler] = {}
        self.running = False
        self.is_connected = False
        
        # Initialize ZMQ context and socket
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.SUB)
        
    def on(self, topic: str, handler: MessageHandler) -> None:
        """Register a handler for a topic.
        
        Args:
            topic: Topic string to match (e.g., "game.event")
            handler: Async function to call with message payload
        """
        self.handlers[topic] = handler
        logger.debug(f"Registered handler for topic: {topic}")
    
    async def run(self) -> None:
        """Start the message processing loop."""
        try:
            # Connect to Lua's PUB socket
            self.socket.connect(self.endpoint)
            # Subscribe to all topics (empty string = all)
            self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
            # Set receive timeout for graceful shutdown checking
            self.socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
            
            self.is_connected = True
            self.running = True
            logger.info(f"ZMQ Router connected to {self.endpoint}")
            
            while self.running:
                try:
                    # Receive message (with timeout for shutdown checking)
                    message = await self.socket.recv_string()
                    await self._process_message(message)
                except zmq.Again:
                    # Timeout - just continue loop to check self.running
                    continue
                except zmq.ZMQError as e:
                    if self.running:  # Only log if not shutting down
                        logger.error(f"ZMQ receive error: {e}")
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"ZMQ Router error: {e}")
            self.is_connected = False
            raise
    
    async def _process_message(self, raw_message: str) -> None:
        """Parse and route a message to its handler.
        
        Args:
            raw_message: Raw message string in format "<topic> <json>"
        """
        try:
            # Find first space to split topic from payload
            space_idx = raw_message.find(" ")
            if space_idx == -1:
                logger.warning(f"Malformed message (no space): {raw_message[:100]}")
                return
            
            topic = raw_message[:space_idx]
            payload_str = raw_message[space_idx + 1:]
            
            # Parse JSON payload
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for topic {topic}: {e}")
                return
            
            # Extract payload (may be nested under "payload" key or direct)
            payload = data.get("payload", data)
            
            logger.debug(f"Received message - topic: {topic}")
            
            # Route to handler
            handler = self.handlers.get(topic)
            if handler:
                try:
                    await handler(payload)
                except Exception as e:
                    logger.error(f"Handler error for {topic}: {e}")
            else:
                logger.warning(f"No handler for topic: {topic}")
                
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the router."""
        logger.info("Shutting down ZMQ Router...")
        self.running = False
        self.is_connected = False
        
        # Give time for loop to exit
        await asyncio.sleep(0.2)
        
        # Close socket and context
        self.socket.close()
        self.context.term()
        logger.info("ZMQ Router shutdown complete")
