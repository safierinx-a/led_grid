use std::io::{self, Read, Write};
use std::time::{Duration, Instant};
use std::thread;

// LED control structures
#[derive(Debug, Clone, Copy)]
struct Pixel {
    r: u8,
    g: u8,
    b: u8,
}

struct LEDController {
    led_count: usize,
    pixels: Vec<Pixel>,
    frame_count: u64,
    last_frame_time: Option<Instant>,
    fps: f64,
}

impl LEDController {
    fn new(led_count: usize) -> Self {
        Self {
            led_count,
            pixels: vec![Pixel { r: 0, g: 0, b: 0 }; led_count],
            frame_count: 0,
            last_frame_time: None,
            fps: 0.0,
        }
    }

    fn process_frame(&mut self, frame_data: &[u8]) -> io::Result<()> {
        // Parse binary frame data
        if frame_data.len() < 10 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Frame too short"));
        }

        // Parse header (version, type, frame_id, width, height)
        let width = u16::from_le_bytes([frame_data[6], frame_data[7]]);
        let height = u16::from_le_bytes([frame_data[8], frame_data[9]]);
        
        // Extract pixel data
        let pixel_data = &frame_data[10..];
        let expected_pixels = (width * height) as usize;
        
        if pixel_data.len() < expected_pixels * 3 {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "Insufficient pixel data"));
        }

        // Convert to pixels
        for i in 0..expected_pixels.min(self.led_count) {
            let idx = i * 3;
            self.pixels[i] = Pixel {
                r: pixel_data[idx],
                g: pixel_data[idx + 1],
                b: pixel_data[idx + 2],
            };
        }

        // Update statistics
        self.frame_count += 1;
        let now = Instant::now();
        
        if let Some(last_time) = self.last_frame_time {
            let delta = now.duration_since(last_time).as_secs_f64();
            if delta > 0.0 {
                let instant_fps = 1.0 / delta;
                self.fps = self.fps * 0.8 + instant_fps * 0.2;
            }
        }
        
        self.last_frame_time = Some(now);

        // Send to hardware (mock implementation)
        self.send_to_hardware()?;

        Ok(())
    }

    fn send_to_hardware(&self) -> io::Result<()> {
        // Mock hardware implementation
        // In real implementation, this would control GPIO pins
        let lit_count = self.pixels.iter().filter(|p| p.r > 0 || p.g > 0 || p.b > 0).count();
        eprintln!("Frame {}: {}/{} pixels lit, FPS: {:.1}", 
                 self.frame_count, lit_count, self.led_count, self.fps);
        Ok(())
    }

    fn send_stats(&self) -> io::Result<()> {
        let stats = format!("{{\"frames_processed\":{},\"fps\":{:.1},\"hardware_type\":\"Rust\"}}", 
                           self.frame_count, self.fps);
        let stats_bytes = stats.as_bytes();
        let length = stats_bytes.len() as u32;
        
        // Send length (4 bytes, little-endian)
        io::stdout().write_all(&length.to_le_bytes())?;
        // Send stats
        io::stdout().write_all(stats_bytes)?;
        io::stdout().flush()?;
        
        Ok(())
    }
}

fn main() -> io::Result<()> {
    // Parse command line arguments
    let args: Vec<String> = std::env::args().collect();
    let mut width = 25;
    let mut height = 24;
    let mut led_pin = 18;
    let mut led_count = 600;

    for i in 1..args.len() {
        match args[i].as_str() {
            "--width" => {
                if i + 1 < args.len() {
                    width = args[i + 1].parse().unwrap_or(25);
                }
            }
            "--height" => {
                if i + 1 < args.len() {
                    height = args[i + 1].parse().unwrap_or(24);
                }
            }
            "--led-pin" => {
                if i + 1 < args.len() {
                    led_pin = args[i + 1].parse().unwrap_or(18);
                }
            }
            "--led-count" => {
                if i + 1 < args.len() {
                    led_count = args[i + 1].parse().unwrap_or(600);
                }
            }
            _ => {}
        }
    }

    eprintln!("Rust LED Controller starting: {}x{}, {} LEDs on pin {}", 
              width, height, led_count, led_pin);

    let mut controller = LEDController::new(led_count);
    let mut frame_count = 0;

    loop {
        // Read frame length (4 bytes, little-endian)
        let mut length_bytes = [0u8; 4];
        match io::stdin().read_exact(&mut length_bytes) {
            Ok(_) => {}
            Err(_) => break, // EOF or error
        }

        let frame_length = u32::from_le_bytes(length_bytes) as usize;
        
        // Read frame data
        let mut frame_data = vec![0u8; frame_length];
        match io::stdin().read_exact(&mut frame_data) {
            Ok(_) => {}
            Err(_) => break, // EOF or error
        }

        // Process frame
        if let Err(e) = controller.process_frame(&frame_data) {
            eprintln!("Error processing frame: {}", e);
            continue;
        }

        frame_count += 1;

        // Send stats periodically
        if frame_count % 30 == 0 {
            if let Err(e) = controller.send_stats() {
                eprintln!("Error sending stats: {}", e);
            }
        }
    }

    eprintln!("Rust LED Controller shutting down");
    Ok(())
} 