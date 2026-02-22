"""ZeroMQ message router - subscribes to Lua PUB socket and routes messages to handlers.

Also provides PUB socket for sending commands to Lua."""

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
    
    Also binds a PUB socket for sending commands to Lua's SUB socket.
    """
    
    def __init__(
        self,
        sub_endpoint: str,
        pub_endpoint: str | None = None,
        context: zmq.asyncio.Context | None = None,
    ):
        """Initialize router.

        Args:
            sub_endpoint: ZMQ endpoint to connect SUB socket to (e.g., "tcp://127.0.0.1:5555")
            pub_endpoint: ZMQ endpoint to bind PUB socket to (e.g., "tcp://*:5556").
                          If None, PUB socket is not created.
            context: Optional shared ZMQ context. When provided the caller owns the
                     context and shutdown() will NOT call context.term(). Required
                     for inproc:// transport where both sockets must share a context.
        """
        self.sub_endpoint = sub_endpoint
        self.pub_endpoint = pub_endpoint
        self.handlers: dict[str, MessageHandler] = {}
        self.running = False
        self.is_connected = False

        # Internal handlers for state responses (request_id -> future)
        self._pending_requests: dict[str, asyncio.Future] = {}

        # Initialize ZMQ context and sockets
        self._owns_context = context is None
        self.context = context if context is not None else zmq.asyncio.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.pub_socket: zmq.asyncio.Socket | None = None

        if pub_endpoint:
            self.pub_socket = self.context.socket(zmq.PUB)
        
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
            # Connect SUB socket to Lua's PUB socket
            self.sub_socket.connect(self.sub_endpoint)
            # Subscribe to all topics (empty string = all)
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
            # Set receive timeout for graceful shutdown checking
            self.sub_socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
            
            logger.info(f"ZMQ Router SUB connected to {self.sub_endpoint}")
            
            # Bind PUB socket if configured
            if self.pub_socket and self.pub_endpoint:
                self.pub_socket.bind(self.pub_endpoint)
                logger.info(f"ZMQ Router PUB bound to {self.pub_endpoint}")
            
            self.is_connected = True
            self.running = True
            
            # Register internal handler for state responses
            self.handlers["state.response"] = self._handle_state_response
            
            while self.running:
                try:
                    # Receive message (with timeout for shutdown checking)
                    # Use recv() with manual decode to handle encoding errors gracefully
                    raw_bytes = await self.sub_socket.recv()
                    try:
                        message = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        # STALKER uses CP1251 internally; latin-1 accepts any byte sequence
                        # and preserves round-trip fidelity for downstream string handling.
                        message = raw_bytes.decode("latin-1")
                        logger.debug("Message decoded with latin-1 (non-UTF-8 bytes, likely CP1251)")
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
            
            # Only log heartbeat messages if explicitly enabled (reduces noise)
            from ..config import settings
            if topic != "system.heartbeat" or settings.log_heartbeat:
                logger.debug(f"Received message - topic: {topic}")
            
            # Route to handler
            handler = self.handlers.get(topic)
            if handler:
                try:
                    await handler(payload)
                except Exception as e:
                    logger.error(f"Handler error for {topic}: {e}")
            else:
                # mic.* topics belong to mic_python service — silently ignore them.
                # Warn for everything else so genuinely missing handlers don't go unnoticed.
                if not topic.startswith("mic."):
                    logger.warning(f"No handler for topic: {topic}")
                
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the router."""
        logger.info("Shutting down ZMQ Router...")
        self.running = False
        self.is_connected = False
        
        # Cancel any pending requests
        for request_id, future in self._pending_requests.items():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        
        # Give time for loop to exit
        await asyncio.sleep(0.2)
        
        # Close sockets with linger timeout
        if self.pub_socket:
            self.pub_socket.setsockopt(zmq.LINGER, 100)  # 100ms linger
            self.pub_socket.close()
        
        self.sub_socket.setsockopt(zmq.LINGER, 100)
        self.sub_socket.close()
        if self._owns_context:
            self.context.term()
        logger.info("ZMQ Router shutdown complete")
    
    async def publish(self, topic: str, payload: dict[str, Any]) -> bool:
        """Publish a message to a topic.
        
        Args:
            topic: Topic string (e.g., "dialogue.display")
            payload: JSON-serializable payload dict
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.pub_socket:
            logger.error("PUB socket not configured - cannot publish")
            return False
        
        if not self.is_connected:
            logger.warning("Not connected - cannot publish")
            return False
        
        try:
            message = f"{topic} {json.dumps(payload)}"
            await self.pub_socket.send_string(message)
            # Only log heartbeat ack if explicitly enabled (reduces noise)
            from ..config import settings
            if topic != "service.heartbeat.ack" or settings.log_heartbeat:
                logger.debug(f"Published to {topic}")
            return True
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False
    
    async def _handle_state_response(self, payload: dict[str, Any]) -> None:
        """Internal handler for state.response messages.
        
        Routes responses to pending request futures based on request_id.
        """
        request_id = payload.get("request_id")
        if not request_id:
            logger.warning("state.response without request_id")
            return
        
        future = self._pending_requests.pop(request_id, None)
        if future and not future.done():
            if "error" in payload:
                future.set_exception(Exception(payload["error"]))
            else:
                future.set_result(payload)
        else:
            logger.warning(f"No pending request for id: {request_id}")
    
    def create_request(self, request_id: str, timeout: float = 30.0) -> asyncio.Future:
        """Create a pending request and return a future.
        
        Args:
            request_id: Unique request identifier
            timeout: Timeout in seconds
            
        Returns:
            Future that will be resolved when response arrives
        """
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        # Set up timeout
        async def timeout_handler():
            await asyncio.sleep(timeout)
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if not future.done():
                    future.set_exception(TimeoutError(f"Request {request_id} timed out"))
        
        asyncio.create_task(timeout_handler())
        return future
