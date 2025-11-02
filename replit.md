# Telegram Raffle Bot

## Overview
This is a Telegram bot designed to manage raffles/lotteries. Users can select raffle numbers, submit payment proof (Binance Pay), and administrators can verify entries. The system tracks tickets, synchronizes data with Google Sheets, and stores information in a PostgreSQL database.

## Purpose
- Allow users to participate in raffles by selecting numbers
- Handle payment verification through administrator approval
- Maintain records in both PostgreSQL database and Google Sheets
- Provide administrative controls for raffle management

## Technologies Used
- **Python** - Main programming language
- **python-telegram-bot** - Telegram bot framework
- **PostgreSQL** (psycopg2-binary) - Primary database
- **Google Sheets API** (gspread, oauth2client) - Data backup and synchronization
- **Google Drive API** - Image storage for payment proofs
- **python-dotenv** - Environment variable management

## Key Features
1. **Raffle Management**
   - Configurable number ranges (00-99, 000-999, 0000-9999)
   - Track available and sold numbers
   - Set custom pricing per ticket

2. **User Flow**
   - `/start` - Begin interaction
   - `/numeros` - Select raffle numbers
   - Submit personal information (name, phone, ID)
   - Upload payment proof
   - Receive confirmation after admin verification

3. **Admin Commands**
   - `/rango` - Configure number range
   - `/precio` - Set ticket price
   - `/estado` - View system status
   - `/pausar` - Pause the bot
   - `/encender` - Reactivate the bot
   - `/reset` - Reset entire system
   - Verify/reject user tickets

## Environment Variables Required
- `TOKEN` - Telegram bot token
- `ADMIN_ID` - Telegram user ID of administrator
- `SHEET_ID` - Google Sheets document ID
- `GOOGLE_SERVICE_ACCOUNT_JSON` - Path to Google service account credentials (default: credenciales.json)
- `CANAL_COMPROBANTES` - Telegram channel ID for payment proofs (optional, defaults to -1002753190289)
- `DATABASE_URL` - PostgreSQL connection string (auto-configured by Replit)

## Project Structure
- `main.py` - Main bot logic and handlers
- `db.py` - Database operations
- `respaldo.py` - Google Sheets backup functions
- `syncer.py` - Database to Sheets synchronization
- `credenciales.json` - Google service account credentials (not in git)
- `tests/` - Test suite

## Recent Changes
- Initial project setup on Replit
- Database and workflow configuration required

## Current State
- **Status**: Needs initial configuration
- **Database**: PostgreSQL required (not yet provisioned)
- **Dependencies**: Python packages need installation
- **Secrets**: Telegram bot token and Google credentials needed
