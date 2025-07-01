#!/usr/bin/env python3
"""
HackAssistant - Hacker AI Assistant CLI Tool
A Python CLI tool that uses Google Gemini API to provide AI responses 
and suggest terminal commands for hackers and developers.
"""

import os
import sys
import subprocess
import json
from typing import Optional, List, Dict, Any
from google import genai
from datetime import datetime


class HackAssistant:
    def __init__(self):
        """Initialize the HackAssistant with API key and conversation history."""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            print("❌ Error: GOOGLE_API_KEY environment variable not set!")
            print("Please set your Google Gemini API key:")
            print("export GOOGLE_API_KEY='your_api_key_here'")
            sys.exit(1)
        
        # Configure the Gemini API
        self.client = genai.Client(api_key=self.api_key)
        
        # Conversation state
        self.conversation_history: List[Dict[str, str]] = []
        self.current_context = {
            "working_directory": os.getcwd(),
            "os_info": self._get_system_info(),
            "session_start": datetime.now().isoformat()
        }
        
        self._display_banner()
        print(f"📁 Working directory: {self.current_context['working_directory']}")
        print(f"💻 System: {self.current_context['os_info']}")
        print(f"🕒 Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n" + "=" * 60)
        print("🎯 COMMANDS:")
        print("  'p' + Enter - New prompt")
        print("  'c' + Enter - Close conversation")
        print("  'y' / 'n' - Accept/Deny suggested commands")
        print("=" * 60)

    def _get_system_info(self) -> str:
        """Get basic system information."""
        try:
            import platform
            return f"{platform.system()} {platform.release()} ({platform.machine()})"
        except Exception:
            return "Unknown Linux system"

    def _create_system_prompt(self) -> str:
        """Create a system prompt with context about the environment."""
        return f"""You are HackAssistant, an AI assistant for hackers and developers working on Linux systems.

Current context:
- Working Directory: {self.current_context['working_directory']}
- System: {self.current_context['os_info']}
- Session started: {self.current_context['session_start']}

Your role:
1. Provide helpful responses for hacking, development, and system administration tasks
2. Suggest specific Linux terminal commands when appropriate
3. Be concise but informative
4. Focus on practical solutions

When suggesting commands:
- Provide ONE specific command that can be executed
- Explain what the command does briefly
- Consider the current working directory context
- Use Linux/bash compatible commands only

Format your response as:
RESPONSE: [Your helpful response here]
COMMAND: [Single terminal command to execute, or NONE if no command needed]

Keep responses focused and actionable for a technical audience."""

    def _add_to_history(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def _get_ai_response(self, user_prompt: str) -> tuple[str, Optional[str]]:
        """Get response from Gemini API."""
        try:
            # Build conversation context
            context_messages = []
            
            # Add system prompt
            system_prompt = self._create_system_prompt()
            
            # Add recent conversation history (last 10 messages)
            recent_history = self.conversation_history[-10:] if len(self.conversation_history) > 10 else self.conversation_history
            
            conversation_context = system_prompt + "\n\nConversation History:\n"
            for msg in recent_history:
                conversation_context += f"{msg['role'].upper()}: {msg['content']}\n"
            
            conversation_context += f"\nUSER: {user_prompt}\n\nRespond in the specified format:"
            
            # Get response from Gemini
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=conversation_context
            )
            ai_response = response.text.strip()
            
            # Parse response and command
            response_text = ""
            suggested_command = None
            
            lines = ai_response.split('\n')
            for line in lines:
                if line.startswith('RESPONSE:'):
                    response_text = line.replace('RESPONSE:', '').strip()
                elif line.startswith('COMMAND:'):
                    cmd = line.replace('COMMAND:', '').strip()
                    if cmd and cmd.upper() != 'NONE':
                        suggested_command = cmd
            
            # If parsing failed, use the whole response
            if not response_text:
                response_text = ai_response
                
            return response_text, suggested_command
            
        except Exception as e:
            return f"❌ Error getting AI response: {str(e)}", None

    def _execute_command(self, command: str) -> str:
        """Execute a terminal command and return output."""
        try:
            print(f"🔧 Executing: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.current_context['working_directory']
            )
            
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            if result.returncode != 0:
                output += f"Return code: {result.returncode}\n"
                
            return output if output else "Command executed successfully (no output)"
            
        except Exception as e:
            return f"❌ Error executing command: {str(e)}"

    def _get_user_choice(self, prompt: str) -> str:
        """Get user input with prompt."""
        try:
            return input(prompt).strip().lower()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            sys.exit(0)

    def _display_banner(self):
        """Display the cool HackAssistant ASCII banner."""
        banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║  ██╗  ██╗ █████╗  ██████╗██╗  ██╗ █████╗ ███████╗███████╗    ║
    ║  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██╔══██╗██╔════╝██╔════╝    ║
    ║  ███████║███████║██║     █████╔╝ ███████║███████╗███████╗    ║
    ║  ██╔══██║██╔══██║██║     ██╔═██╗ ██╔══██║╚════██║╚════██║    ║
    ║  ██║  ██║██║  ██║╚██████╗██║  ██╗██║  ██║███████║███████║    ║
    ║  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝    ║
    ║                                                               ║
    ║              █████╗ ███████╗███████╗██╗███████╗████████╗      ║
    ║             ██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝      ║
    ║             ███████║███████╗███████╗██║███████╗   ██║         ║
    ║             ██╔══██║╚════██║╚════██║██║╚════██║   ██║         ║
    ║             ██║  ██║███████║███████║██║███████║   ██║         ║
    ║             ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝         ║
    ║                                                               ║
    ║                    🔥 HACKER AI ASSISTANT 🔥                  ║
    ║                  🤖 Powered by Google Gemini 🤖               ║
    ║                                                               ║
    ║              [⚡] Ready for Security Research [⚡]             ║
    ║              [🛡️ ] System Administration [🛡️ ]              ║
    ║              [💻] Development Tasks [💻]                     ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
        """
        
        # Print banner with colors
        print("\033[92m" + banner + "\033[0m")  # Green color
        print("\033[91m🚨 WARNING: For legitimate security research only! 🚨\033[0m")  # Red warning

    def run(self):
        """Main conversation loop."""
        print("\n💬 Enter your first prompt (or 'c' to close):")
        
        while True:
            try:
                # Get user input
                user_input = input("🔥 hackassistant> ").strip()
                
                if not user_input:
                    continue
                    
                # Handle special commands
                if user_input.lower() == 'c':
                    print("👋 Closing conversation. Goodbye!")
                    break
                elif user_input.lower() == 'p':
                    print("💬 Enter your prompt:")
                    continue
                
                # Add user message to history
                self._add_to_history("user", user_input)
                
                # Get AI response
                print("🤖 Thinking...")
                ai_response, suggested_command = self._get_ai_response(user_input)
                
                # Display AI response
                print(f"\n🤖 AI Response:")
                print(f"{ai_response}")
                
                # Add AI response to history
                self._add_to_history("assistant", ai_response)
                
                # Handle suggested command
                if suggested_command:
                    print(f"\n💡 Suggested command:")
                    print(f"📋 {suggested_command}")
                    
                    choice = self._get_user_choice("\n❓ Execute this command? (y/n): ")
                    
                    if choice == 'y':
                        command_output = self._execute_command(suggested_command)
                        print(f"\n📤 Command Output:")
                        print(command_output)
                        
                        # Add command and output to history for context
                        self._add_to_history("system", f"Executed command: {suggested_command}")
                        self._add_to_history("system", f"Command output: {command_output}")
                        
                        # Continue the conversation automatically
                        print(f"\n🔄 Continue working... (enter 'p' for new prompt, 'c' to close)")
                        
                    elif choice == 'n':
                        print("❌ Command declined.")
                        print("💬 Enter new prompt (or 'p' for prompt mode, 'c' to close):")
                    else:
                        print("❓ Invalid choice. Please enter 'y' or 'n'")
                        
                else:
                    print("💬 Enter new prompt (or 'p' for prompt mode, 'c' to close):")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")
                print("💬 Enter new prompt (or 'c' to close):")


def main():
    """Main entry point."""
    try:
        assistant = HackAssistant()
        assistant.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
