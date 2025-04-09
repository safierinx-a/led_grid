const WebSocket = require("ws");

// Configuration
const PORT = process.env.PORT || 8080;
const GRID_WIDTH = parseInt(process.env.GRID_WIDTH || "25");
const GRID_HEIGHT = parseInt(process.env.GRID_HEIGHT || "24");
const SIMULATE_LATENCY = process.env.SIMULATE_LATENCY === "true";
const MAX_LATENCY_MS = parseInt(process.env.MAX_LATENCY_MS || "200");
const SIMULATE_PACKET_LOSS = process.env.SIMULATE_PACKET_LOSS === "true";
const PACKET_LOSS_RATE = parseFloat(process.env.PACKET_LOSS_RATE || "0.05"); // 5% packet loss
const USE_DELTA_COMPRESSION = process.env.USE_DELTA_COMPRESSION !== "false"; // Default to true
const USE_BINARY_FORMAT = process.env.USE_BINARY_FORMAT !== "false"; // Default to true
const MAX_HISTORY_ENTRIES = parseInt(process.env.MAX_HISTORY_ENTRIES || "60"); // Maximum history entries
const MAX_CLIENTS = parseInt(process.env.MAX_CLIENTS || "10"); // Maximum number of clients
const LOG_LEVEL = process.env.LOG_LEVEL || "info"; // debug, info, warn, error

// Logging utility
const logger = {
  debug: (...args) => {
    if (LOG_LEVEL === "debug") console.log(...args);
  },
  info: (...args) => {
    if (LOG_LEVEL === "debug" || LOG_LEVEL === "info") console.log(...args);
  },
  warn: (...args) => {
    if (LOG_LEVEL !== "error") console.warn(...args);
  },
  error: (...args) => {
    console.error(...args);
  },
};

// Create WebSocket server
const wss = new WebSocket.Server({ port: PORT });

logger.info(`Mock LED Controller starting on port ${PORT}`);
logger.info(`Grid dimensions: ${GRID_WIDTH}x${GRID_HEIGHT}`);
if (SIMULATE_LATENCY) {
  logger.info(`Latency simulation enabled (0-${MAX_LATENCY_MS}ms)`);
}
if (SIMULATE_PACKET_LOSS) {
  logger.info(`Packet loss simulation enabled (${PACKET_LOSS_RATE * 100}%)`);
}
logger.info(
  `Delta compression: ${USE_DELTA_COMPRESSION ? "enabled" : "disabled"}`
);
logger.info(`Binary format: ${USE_BINARY_FORMAT ? "enabled" : "disabled"}`);

// System monitoring stats
let stats = {
  startTime: Date.now(),
  bytesReceived: 0,
  bytesSent: 0,
  framesReceived: 0,
  framesDropped: 0,
  lastFrameTime: null,
  fps: 0,
  fpsHistory: [],
  bandwidth: {
    in: 0, // bytes per second
    out: 0, // bytes per second
  },
  clients: 0,
  latency: {
    min: 0,
    max: 0,
    avg: 0,
  },
  deltaFramePercent: 0,
  memory: {},
};

// Track connected clients
let serverConfig = {
  width: GRID_WIDTH,
  height: GRID_HEIGHT,
};

// Last received frame for visualization - limit to 1 frame buffer
let lastFrame = null;

// Store previous frame for delta compression - limit to 1 frame buffer
let previousFrame = null;

// Memory usage monitoring
function updateMemoryStats() {
  const memoryUsage = process.memoryUsage();
  stats.memory = {
    rss: memoryUsage.rss, // Resident Set Size - total memory allocated
    heapTotal: memoryUsage.heapTotal, // Total size of allocated heap
    heapUsed: memoryUsage.heapUsed, // Actual memory used
    external: memoryUsage.external, // Memory used by C++ objects bound to JS
    arrayBuffers: memoryUsage.arrayBuffers || 0, // Memory used by ArrayBuffers and SharedArrayBuffers
  };

  // Log memory warning if heap usage is more than 75% of total
  if (stats.memory.heapUsed > stats.memory.heapTotal * 0.75) {
    logger.warn(
      `High memory usage: ${formatBytes(stats.memory.heapUsed)}/${formatBytes(
        stats.memory.heapTotal
      )} (${Math.round(
        (stats.memory.heapUsed / stats.memory.heapTotal) * 100
      )}%)`
    );

    // Force garbage collection if exposed (only in --expose-gc mode)
    if (global.gc) {
      logger.info("Forcing garbage collection");
      global.gc();
    }
  }
}

// Function to calculate and apply delta compression
function createDeltaFrame(newFrame, previousFrame) {
  if (!previousFrame || !previousFrame.pixels || !newFrame.pixels) {
    return newFrame; // No delta possible
  }

  const deltaFrame = {
    ...newFrame,
    isDelta: true,
    changes: [],
  };

  // Remove full pixels array to save bandwidth
  delete deltaFrame.pixels;

  // Compare pixels and record only the changes
  for (let i = 0; i < newFrame.pixels.length; i += 3) {
    const r1 = newFrame.pixels[i];
    const g1 = newFrame.pixels[i + 1];
    const b1 = newFrame.pixels[i + 2];

    const r2 = previousFrame.pixels[i] || 0;
    const g2 = previousFrame.pixels[i + 1] || 0;
    const b2 = previousFrame.pixels[i + 2] || 0;

    // If pixel changed, add to changes
    // Use a small threshold to ignore minor color variations
    if (
      Math.abs(r1 - r2) > 2 ||
      Math.abs(g1 - g2) > 2 ||
      Math.abs(b1 - b2) > 2
    ) {
      const pixelIndex = i / 3;
      const x = pixelIndex % GRID_WIDTH;
      const y = Math.floor(pixelIndex / GRID_WIDTH);

      deltaFrame.changes.push({
        x,
        y,
        r: r1,
        g: g1,
        b: b1,
      });
    }
  }

  // If too many changes (>75% of pixels), just send full frame
  // This is a more aggressive threshold than before (was 50%)
  if (
    deltaFrame.changes.length === 0 ||
    deltaFrame.changes.length > (newFrame.pixels.length / 3) * 0.75
  ) {
    return newFrame;
  }

  return deltaFrame;
}

// Function to reconstruct a full frame from a delta frame
function applyDeltaFrame(deltaFrame, previousFrame) {
  if (!deltaFrame.isDelta || !previousFrame || !previousFrame.pixels) {
    return deltaFrame; // Not a delta or can't apply
  }

  // Create a copy of the previous frame's pixels
  const pixels = [...previousFrame.pixels];

  // Apply each change
  for (const change of deltaFrame.changes) {
    const index = (change.y * GRID_WIDTH + change.x) * 3;
    pixels[index] = change.r;
    pixels[index + 1] = change.g;
    pixels[index + 2] = change.b;
  }

  // Create a new full frame with the updated pixels
  return {
    ...deltaFrame,
    pixels,
    isDelta: false,
  };
}

// Count FPS every second
setInterval(() => {
  // Calculate instantaneous FPS based on frames received in the last second
  const now = Date.now();
  const framesSinceLastCheck =
    stats.framesReceived - (stats.lastFpsCheckFrameCount || 0);

  // Only log significant FPS changes
  if (framesSinceLastCheck > 0) {
    logger.debug(
      `FPS calculation: ${framesSinceLastCheck} frames since last check`
    );
  }

  // Store current count for next calculation
  stats.lastFpsCheckFrameCount = stats.framesReceived;

  // Add to FPS history
  stats.fpsHistory.push(framesSinceLastCheck);

  // Keep only limited history to avoid memory leaks
  if (stats.fpsHistory.length > MAX_HISTORY_ENTRIES) {
    stats.fpsHistory.shift();
  }

  // Calculate rolling average FPS (last 5 seconds)
  const recentHistory = stats.fpsHistory.slice(-5);
  const prevFps = stats.fps;

  if (recentHistory.length > 0) {
    stats.fps = Math.round(
      recentHistory.reduce((a, b) => a + b, 0) / recentHistory.length
    );
  }

  // Only log if FPS changed significantly
  if (Math.abs(prevFps - stats.fps) > 5) {
    logger.info(`FPS changed: ${prevFps} → ${stats.fps}`);
  }

  // Update memory stats
  updateMemoryStats();
}, 1000);

// Update stats every 5 seconds
setInterval(() => {
  // Calculate bandwidth
  const elapsedSeconds = (Date.now() - stats.startTime) / 1000;
  stats.bandwidth.in = Math.round(stats.bytesReceived / elapsedSeconds);
  stats.bandwidth.out = Math.round(stats.bytesSent / elapsedSeconds);

  // Calculate compression statistics
  const totalDeltaFrames = Array.from(wss.clients).reduce(
    (sum, client) => sum + (client.clientStats?.deltaFramesSent || 0),
    0
  );

  const totalFullFrames = Array.from(wss.clients).reduce(
    (sum, client) => sum + (client.clientStats?.fullFramesSent || 0),
    0
  );

  const totalFramesSent = totalDeltaFrames + totalFullFrames;

  stats.deltaFramePercent =
    totalFramesSent > 0
      ? Math.round((totalDeltaFrames / totalFramesSent) * 100)
      : 0;

  // Log current stats (less verbose)
  logger.info(`=== STATS ===`);
  logger.info(
    `Clients: ${stats.clients} | Frames: ${stats.framesReceived} (${stats.framesDropped} dropped) | FPS: ${stats.fps}`
  );
  logger.info(
    `Bandwidth: IN ${formatBytes(stats.bandwidth.in)}/s, OUT ${formatBytes(
      stats.bandwidth.out
    )}/s`
  );
  logger.info(
    `Total: IN ${formatBytes(stats.bytesReceived)}, OUT ${formatBytes(
      stats.bytesSent
    )}`
  );
  logger.info(
    `Memory: RSS ${formatBytes(stats.memory.rss)}, Heap ${formatBytes(
      stats.memory.heapUsed
    )}/${formatBytes(stats.memory.heapTotal)}`
  );

  if (totalFramesSent > 0) {
    logger.info(
      `Compression: ${stats.deltaFramePercent}% delta frames (${totalDeltaFrames} delta / ${totalFullFrames} full)`
    );
  }

  // Only visualize frame if debug logging is enabled
  if (LOG_LEVEL === "debug" && lastFrame && lastFrame.pixels) {
    visualizeFrame(lastFrame);
  }

  // Limit number of clients to prevent memory issues
  if (wss.clients.size > MAX_CLIENTS) {
    logger.warn(
      `Too many clients (${wss.clients.size}/${MAX_CLIENTS}), dropping oldest connection`
    );
    // Get the oldest client
    const oldestClient = Array.from(wss.clients).reduce((oldest, client) => {
      if (
        !oldest ||
        (client.clientStats &&
          oldest.clientStats &&
          client.clientStats.connectTime < oldest.clientStats.connectTime)
      ) {
        return client;
      }
      return oldest;
    }, null);

    if (oldestClient) {
      oldestClient.close(1000, "Server reached maximum client limit");
    }
  }
}, 5000);

// Helper function to format bytes
function formatBytes(bytes, decimals = 2) {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

// Helper function to visualize a frame in the console
function visualizeFrame(frame) {
  // Only show a simple representation to avoid terminal spam
  const width = frame.width || GRID_WIDTH;
  const height = frame.height || GRID_HEIGHT;

  console.log(`\nFrame preview (${width}x${height}):`);
  let preview = "";

  // Sample pixels from the frame to create a small preview
  const sampleWidth = Math.min(width, 15);
  const sampleHeight = Math.min(height, 8);
  const xStep = width / sampleWidth;
  const yStep = height / sampleHeight;

  for (let y = 0; y < sampleHeight; y++) {
    let row = "";
    for (let x = 0; x < sampleWidth; x++) {
      const srcX = Math.floor(x * xStep);
      const srcY = Math.floor(y * yStep);
      const pixelIndex = (srcY * width + srcX) * 3; // RGB values

      if (frame.pixels && pixelIndex < frame.pixels.length - 2) {
        const brightness =
          Math.max(
            frame.pixels[pixelIndex],
            frame.pixels[pixelIndex + 1],
            frame.pixels[pixelIndex + 2]
          ) > 127
            ? "█"
            : "▒";
        row += brightness;
      } else {
        row += "░";
      }
    }
    preview += row + "\n";
  }

  console.log(preview);
}

// Convert frame to binary format
// Format:
// - 1 byte: protocol version (1)
// - 1 byte: message type (1 = frame, 2 = delta frame)
// - 4 bytes: frame ID (uint32)
// - 2 bytes: width (uint16)
// - 2 bytes: height (uint16)
// - Remaining bytes: RGB pixel data (1 byte per channel)
function frameToBinary(frame) {
  // Calculate buffer size
  const headerSize = 10; // 10 bytes for header
  const pixelDataSize = frame.pixels.length; // 1 byte per value (R,G,B)

  // Create buffer
  const buffer = Buffer.alloc(headerSize + pixelDataSize);

  // Write header
  buffer.writeUInt8(1, 0); // Protocol version
  buffer.writeUInt8(1, 1); // Message type (1 = frame)

  // Parse and write frame ID as an integer
  const frameIdNum = parseInt(frame.id.replace(/\D/g, "").slice(0, 8), 16) || 0;
  buffer.writeUInt32LE(frameIdNum, 2); // Frame ID (4 bytes)

  buffer.writeUInt16LE(frame.width || GRID_WIDTH, 6); // Width
  buffer.writeUInt16LE(frame.height || GRID_HEIGHT, 8); // Height

  // Write pixel data
  for (let i = 0; i < frame.pixels.length; i++) {
    buffer.writeUInt8(frame.pixels[i], headerSize + i);
  }

  return buffer;
}

// Convert delta frame to binary format
// Format:
// - 1 byte: protocol version (1)
// - 1 byte: message type (2 = delta frame)
// - 4 bytes: frame ID (uint32)
// - 2 bytes: width (uint16)
// - 2 bytes: height (uint16)
// - 2 bytes: number of changes (uint16)
// - For each change:
//   - 2 bytes: x (uint16)
//   - 2 bytes: y (uint16)
//   - 3 bytes: RGB
function deltaFrameToBinary(deltaFrame) {
  // Calculate buffer size
  const headerSize = 12; // 12 bytes for header
  const changeSize = 7; // 7 bytes per change (2 for x, 2 for y, 3 for RGB)
  const changesDataSize = deltaFrame.changes.length * changeSize;

  // Create buffer
  const buffer = Buffer.alloc(headerSize + changesDataSize);

  // Write header
  buffer.writeUInt8(1, 0); // Protocol version
  buffer.writeUInt8(2, 1); // Message type (2 = delta frame)

  // Parse and write frame ID as an integer
  const frameIdNum =
    parseInt(deltaFrame.id.replace(/\D/g, "").slice(0, 8), 16) || 0;
  buffer.writeUInt32LE(frameIdNum, 2); // Frame ID (4 bytes)

  buffer.writeUInt16LE(deltaFrame.width || GRID_WIDTH, 6); // Width
  buffer.writeUInt16LE(deltaFrame.height || GRID_HEIGHT, 8); // Height
  buffer.writeUInt16LE(deltaFrame.changes.length, 10); // Number of changes

  // Write changes
  let offset = headerSize;
  for (let i = 0; i < deltaFrame.changes.length; i++) {
    const change = deltaFrame.changes[i];
    buffer.writeUInt16LE(change.x, offset); // X
    buffer.writeUInt16LE(change.y, offset + 2); // Y
    buffer.writeUInt8(change.r, offset + 4); // R
    buffer.writeUInt8(change.g, offset + 5); // G
    buffer.writeUInt8(change.b, offset + 6); // B
    offset += changeSize;
  }

  return buffer;
}

// Parse binary frame
function parseBinaryFrame(buffer) {
  // Read header
  const version = buffer.readUInt8(0);
  const messageType = buffer.readUInt8(1);
  const frameId = buffer.readUInt32LE(2).toString(16).padStart(8, "0");
  const width = buffer.readUInt16LE(6);
  const height = buffer.readUInt16LE(8);

  if (messageType === 1) {
    // Regular frame
    const headerSize = 10;
    const pixels = [];

    // Read pixel data
    for (let i = 0; i < width * height * 3; i++) {
      pixels.push(buffer.readUInt8(headerSize + i));
    }

    return {
      id: frameId,
      type: "frame",
      width,
      height,
      pixels,
      source: "binary_decoder",
    };
  } else if (messageType === 2) {
    // Delta frame
    const headerSize = 12;
    const numChanges = buffer.readUInt16LE(10);
    const changes = [];

    // Read changes
    let offset = headerSize;
    for (let i = 0; i < numChanges; i++) {
      changes.push({
        x: buffer.readUInt16LE(offset),
        y: buffer.readUInt16LE(offset + 2),
        r: buffer.readUInt8(offset + 4),
        g: buffer.readUInt8(offset + 5),
        b: buffer.readUInt8(offset + 6),
      });
      offset += 7;
    }

    return {
      id: frameId,
      type: "frame",
      isDelta: true,
      width,
      height,
      changes,
      source: "binary_decoder",
    };
  }

  return null;
}

// Handle connections
wss.on("connection", (ws) => {
  // Enforce max clients limit
  if (wss.clients.size > MAX_CLIENTS) {
    logger.warn(
      `Rejecting connection: Maximum clients (${MAX_CLIENTS}) reached`
    );
    ws.close(1000, "Server reached maximum client limit");
    return;
  }

  logger.info("Client connected");
  stats.clients++;

  // Client-specific stats
  const clientStats = {
    connectTime: Date.now(),
    framesReceived: 0,
    bytesReceived: 0,
    bytesSent: 0,
    fullFramesSent: 0,
    deltaFramesSent: 0,
    compressionRatio: 0,
  };

  // Attach stats to the client for global calculations
  ws.clientStats = clientStats;

  // Weak references to cached frames to allow garbage collection
  ws.frameCache = new Map();

  // Clean up function to handle proper resource cleanup
  const cleanupClient = () => {
    stats.clients--;

    // Clear any timers associated with this client
    if (ws.statsInterval) {
      clearInterval(ws.statsInterval);
      ws.statsInterval = null;
    }

    // Clear the frame cache to allow garbage collection
    if (ws.frameCache) {
      ws.frameCache.clear();
      ws.frameCache = null;
    }

    // Remove circular references
    ws.previousFrame = null;
    ws.clientStats = null;

    // Force garbage collection if exposed
    if (global.gc) {
      global.gc();
    }

    logger.info("Client disconnected and resources cleaned up");
  };

  // Send initial status
  const initialStatus = JSON.stringify({
    type: "status",
    status: "connected",
    config: serverConfig,
    binary_supported: true,
  });

  ws.send(initialStatus);
  stats.bytesSent += initialStatus.length;
  clientStats.bytesSent += initialStatus.length;

  // Handle messages
  ws.on("message", (message) => {
    try {
      // Update stats
      const messageSize = message.length || message.byteLength;
      stats.bytesReceived += messageSize;
      clientStats.bytesReceived += messageSize;

      // Simulate packet loss
      if (SIMULATE_PACKET_LOSS && Math.random() < PACKET_LOSS_RATE) {
        stats.framesDropped++;
        logger.debug("Simulating packet loss - dropping frame");
        return;
      }

      // Check if this is a binary message
      let data;
      if (message instanceof Buffer) {
        // Try to parse as binary frame
        data = parseBinaryFrame(message);
        if (!data) {
          logger.warn("Received invalid binary message");
          return;
        }
      } else {
        // Parse as JSON
        data = JSON.parse(message.toString());
      }

      // Only log message type if in debug mode
      logger.debug(`Received message type: ${data.type || "undefined"}`);

      // Process based on message type
      let response;

      if (data.type === "config") {
        // Handle configuration update
        serverConfig = {
          width: data.width || serverConfig.width,
          height: data.height || serverConfig.height,
        };

        logger.info(
          `Updated configuration: ${serverConfig.width}x${serverConfig.height}`
        );

        // Acknowledge configuration
        response = JSON.stringify({
          type: "config_ack",
          config: serverConfig,
          stats: {
            uptime: Math.round((Date.now() - stats.startTime) / 1000),
            fps: stats.fps,
            bandwidth: stats.bandwidth,
            frames_received: stats.framesReceived,
            frames_dropped: stats.framesDropped,
          },
        });
      } else if (data.type === "pattern") {
        // Just acknowledge pattern changes
        response = JSON.stringify({
          type: "pattern_ack",
          pattern: data.data,
        });
      } else if (
        data.type === "frame" ||
        data.pixels ||
        (data.isDelta && data.changes)
      ) {
        // Better frame detection - recognize all frame formats:
        // 1. Explicit frame type
        // 2. Message with pixels array
        // 3. Delta frame with changes array

        // Update frame stats
        stats.framesReceived++;
        clientStats.framesReceived++;
        stats.lastFrameTime = Date.now();

        // Check if this is a delta frame that needs to be reconstructed
        let fullFrame = data;
        if (data.isDelta && previousFrame) {
          fullFrame = applyDeltaFrame(data, previousFrame);
          logger.debug(
            `Applied delta frame with ${data.changes.length} pixel changes`
          );
        }

        // Store frame for visualization
        lastFrame = fullFrame;

        // Store for future delta comparison
        previousFrame = fullFrame;

        // Only log every 100th frame to reduce noise
        if (stats.framesReceived % 100 === 0) {
          logger.info(
            `Received frame #${stats.framesReceived} from ${
              data.source || "unknown"
            }`
          );
        }

        // Acknowledge the frame - include binary format flag
        response = JSON.stringify({
          type: "frame_ack",
          id: data.id,
          binary_supported: true,
          stats: {
            fps: stats.fps,
            frames_received: stats.framesReceived,
            frames_dropped: stats.framesDropped,
          },
        });
      } else if (data.type === "stats_request") {
        logger.debug("Received stats request");
        // Send detailed stats
        response = JSON.stringify({
          type: "stats_response",
          system: {
            uptime: Math.round((Date.now() - stats.startTime) / 1000),
            memory: process.memoryUsage(),
            clients: stats.clients,
          },
          performance: {
            fps: stats.fps,
            bandwidth_in: stats.bandwidth.in,
            bandwidth_out: stats.bandwidth.out,
            frames_received: stats.framesReceived,
            frames_dropped: stats.framesDropped,
            bytes_received: stats.bytesReceived,
            bytes_sent: stats.bytesSent,
            delta_frame_percent: stats.deltaFramePercent || 0,
          },
          client: {
            connect_time: clientStats.connectTime,
            frames_received: clientStats.framesReceived,
            bytes_received: clientStats.bytesReceived,
            bytes_sent: clientStats.bytesSent,
            delta_frames: clientStats.deltaFramesSent,
            full_frames: clientStats.fullFramesSent,
            compression_ratio: clientStats.compressionRatio,
          },
        });
      } else if (data.type === "simulation_config") {
        // Handle simulation configuration
        if (data.simulate_latency !== undefined) {
          SIMULATE_LATENCY = data.simulate_latency;
          logger.info(
            `Latency simulation ${SIMULATE_LATENCY ? "enabled" : "disabled"}`
          );
        }

        if (data.simulate_packet_loss !== undefined) {
          SIMULATE_PACKET_LOSS = data.simulate_packet_loss;
          logger.info(
            `Packet loss simulation ${
              SIMULATE_PACKET_LOSS ? "enabled" : "disabled"
            }`
          );
        }

        // Acknowledge config changes
        response = JSON.stringify({
          type: "simulation_config_ack",
          simulate_latency: SIMULATE_LATENCY,
          simulate_packet_loss: SIMULATE_PACKET_LOSS,
        });
      }

      // Send response with optional latency simulation
      if (response) {
        if (SIMULATE_LATENCY) {
          const latency = Math.floor(Math.random() * MAX_LATENCY_MS);
          setTimeout(() => {
            ws.send(response);
            stats.bytesSent += response.length;
            clientStats.bytesSent += response.length;
          }, latency);
        } else {
          ws.send(response);
          stats.bytesSent += response.length;
          clientStats.bytesSent += response.length;
        }
      }
    } catch (error) {
      logger.error("Error handling message:", error);
    }
  });

  // Send periodic stats to client
  ws.statsInterval = setInterval(() => {
    const statsUpdate = JSON.stringify({
      type: "stats_update",
      timestamp: Date.now(),
      fps: stats.fps,
      bandwidth: stats.bandwidth,
      frames_received: stats.framesReceived,
      frames_dropped: stats.framesDropped,
      delta_frame_percent: stats.deltaFramePercent || 0,
      memory: {
        rss: stats.memory.rss,
        heapUsed: stats.memory.heapUsed,
        heapTotal: stats.memory.heapTotal,
      },
    });

    ws.send(statsUpdate);
    stats.bytesSent += statsUpdate.length;
    clientStats.bytesSent += statsUpdate.length;
  }, 10000); // Every 10 seconds

  // Handle disconnection with proper cleanup
  ws.on("close", () => {
    cleanupClient();
  });

  // Handle errors with proper cleanup
  ws.on("error", (error) => {
    logger.error(`WebSocket error: ${error.message}`);
    cleanupClient();
  });
});
