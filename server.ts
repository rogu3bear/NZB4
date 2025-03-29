import express, { Request, Response, NextFunction } from 'express';
import { body, validationResult } from 'express-validator';
import bodyParser from 'body-parser';
import morgan from 'morgan';
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import * as fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { v4 as uuidv4 } from 'uuid';
import winston from 'winston';
import { convertMedia } from './conversion';
import { validateRequestData } from './validation';

// Type definitions
interface ConversionRequest {
  source_path: string;
  target_format: string;
}

interface ErrorResponse {
  error: string;
  requestId?: string;
  details?: any;
}

interface SuccessResponse {
  message: string;
  output: string;
  format: string;
  processing_time: string;
  requestId: string;
}

// Configure logging
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  defaultMeta: { service: 'media-converter' },
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

// Configure application
const app = express();
const PORT: number = parseInt(process.env.PORT || '3000', 10);
const OUTPUT_DIR: string = process.env.OUTPUT_DIR || '/complete';
const DOWNLOAD_DIR: string = process.env.DOWNLOAD_DIR || '/downloads';
const ALLOWED_FORMATS: string[] = ['mp4', 'mov'];

// Check that directories exist
[OUTPUT_DIR, DOWNLOAD_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    try {
      fs.mkdirSync(dir, { recursive: true });
      logger.info(`Created directory: ${dir}`);
    } catch (error) {
      logger.error(`Failed to create directory: ${dir}`, { error });
    }
  }
});

// Request ID middleware
app.use((req: Request, res: Response, next: NextFunction) => {
  req.headers['x-request-id'] = req.headers['x-request-id'] || uuidv4();
  res.setHeader('X-Request-ID', req.headers['x-request-id'] as string);
  next();
});

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*',
  methods: ['GET', 'POST'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID']
}));

// Request parsing middleware
app.use(bodyParser.json({ limit: '50mb' }));
app.use(morgan('combined'));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  standardHeaders: true,
  legacyHeaders: false,
  message: 'Too many requests from this IP, please try again later'
});
app.use(limiter);

// Path sanitization function
function sanitizePath(inputPath: string): string {
  // Remove any directory traversal sequences and normalize
  const normalized = path.normalize(inputPath).replace(/^(\.\.(\/|\\|$))+/, '');
  // Remove any characters that could be used for injection
  return normalized.replace(/[&/\\#,+()$~%'":*?<>{}]/g, '');
}

// Validate media source input
function validateMediaSource(source: string): { isValid: boolean; message: string } {
  if (!source) {
    return { isValid: false, message: 'Source path is required' };
  }
  
  // URL validation for remote sources
  if (source.startsWith('http')) {
    try {
      new URL(source);
      return { isValid: true, message: 'Valid URL' };
    } catch {
      return { isValid: false, message: 'Invalid URL format' };
    }
  }
  
  // File path validation for local sources
  if (fs.existsSync(source)) {
    return { isValid: true, message: 'Valid file path' };
  }
  
  return { isValid: false, message: 'Source file not found or inaccessible' };
}

// Media conversion function (simulated)
async function convertMedia(
  sourcePath: string, 
  outputDir: string, 
  targetFormat: string = 'mp4',
  downloadDir: string = '/downloads'
): Promise<string> {
  return new Promise((resolve, reject) => {
    // Create a safe filename for output
    const safeFilename = path.basename(sourcePath)
      .replace(/\.[^/.]+$/, '')  // Remove extension
      .replace(/[^a-zA-Z0-9-_]/g, '_'); // Replace unsafe chars
    
    const outputPath = path.join(outputDir, `${safeFilename}.${targetFormat}`);
    
    logger.info(`Converting ${sourcePath} to ${outputPath}`);
    
    // In a real implementation, this would call the Python converter or other process
    // For now, we'll simulate the conversion
    setTimeout(() => {
      // Simulate successful conversion
      if (Math.random() > 0.1) { // 90% success rate
        resolve(outputPath);
      } else {
        reject(new Error('Conversion failed'));
      }
    }, 2000);  // Simulate 2 second processing time
  });
}

// Validation middleware for the convert endpoint
const validateConvertInput = [
  body('source_path').notEmpty().withMessage('Source path is required'),
  body('target_format')
    .optional()
    .isIn(ALLOWED_FORMATS)
    .withMessage(`Target format must be one of: ${ALLOWED_FORMATS.join(', ')}`)
];

// API Endpoints
app.post(
  '/convert',
  validateConvertInput,
  async (req: Request, res: Response) => {
    const requestId = req.headers['x-request-id'] as string;
    const startTime = Date.now();
    
    try {
      // Check validation errors from middleware
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        logger.warn(`Validation failed: ${JSON.stringify(errors.array())}`, { requestId });
        return res.status(400).json({ 
          error: 'Validation failed', 
          details: errors.array(),
          requestId 
        });
      }

      const data = req.body as ConversionRequest;
      const sourcePath = data.source_path;
      const targetFormat = data.target_format || 'mp4';
      
      // Additional validation
      const sourceValidation = validateMediaSource(sourcePath);
      if (!sourceValidation.isValid) {
        logger.warn(`Source validation failed: ${sourceValidation.message}`, { requestId });
        return res.status(400).json({ 
          error: sourceValidation.message,
          requestId
        });
      }
      
      // Process media conversion
      logger.info(`Starting conversion: ${sourcePath} to ${targetFormat}`, { requestId });
      const outputPath = await convertMedia(
        sourcePath,
        OUTPUT_DIR,
        targetFormat,
        DOWNLOAD_DIR
      );
      
      const processingTime = ((Date.now() - startTime) / 1000).toFixed(2);
      logger.info(`Conversion completed in ${processingTime}s`, { requestId, outputPath });
      
      const response: SuccessResponse = {
        message: 'Conversion successful',
        output: outputPath,
        format: targetFormat,
        processing_time: `${processingTime}s`,
        requestId
      };
      
      return res.status(200).json(response);
    } catch (error) {
      const processingTime = ((Date.now() - startTime) / 1000).toFixed(2);
      logger.error(`Conversion failed after ${processingTime}s: ${error instanceof Error ? error.message : 'Unknown error'}`, { 
        requestId,
        error: error instanceof Error ? error.stack : error
      });
      
      const errorResponse: ErrorResponse = {
        error: 'An error occurred during conversion',
        requestId
      };
      
      return res.status(500).json(errorResponse);
    }
  }
);

app.get('/status', (req: Request, res: Response) => {
  const requestId = req.headers['x-request-id'] as string;
  
  res.status(200).json({
    status: 'operational',
    version: '1.0.0',
    output_dir: OUTPUT_DIR,
    download_dir: DOWNLOAD_DIR,
    requestId
  });
});

// 404 handler
app.use((req: Request, res: Response) => {
  logger.warn(`Resource not found: ${req.method} ${req.path}`, {
    requestId: req.headers['x-request-id']
  });
  
  res.status(404).json({ 
    error: 'Resource not found',
    requestId: req.headers['x-request-id']
  });
});

// Global error handler
app.use((error: Error, req: Request, res: Response, next: NextFunction) => {
  const requestId = req.headers['x-request-id'] as string;
  
  logger.error(`Unhandled error: ${error.message}`, {
    requestId,
    error: error.stack
  });
  
  res.status(500).json({
    error: 'An unexpected error occurred',
    requestId
  });
});

// Start the server
app.listen(PORT, () => {
  logger.info(`Server is running on port ${PORT}`);
}); 