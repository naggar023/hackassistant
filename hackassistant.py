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
5. Reference and analyze previous command outputs when relevant
6. Detect errors in command outputs and suggest fixes

When analyzing conversations:
- Pay attention to EXECUTED commands and their OUTPUT
- Use command outputs to provide context-aware suggestions
- Build upon previous results and findings
- Reference specific details from command outputs when helpful
- Identify failed commands (non-zero return codes, error messages)
- Suggest corrective actions for errors

Error Analysis Guidelines:
- Look for permission denied errors (suggest sudo)
- Check for missing packages (suggest installation)
- Identify network issues (suggest connectivity checks)
- Detect syntax errors (suggest corrections)
- Notice missing files/directories (suggest creation or path fixes)

When suggesting commands:
- Provide ONE specific command that can be executed
- Explain what the command does briefly
- Consider the current working directory context
- Use Linux/bash compatible commands only
- Build upon previous command results when appropriate
- If previous command failed, prioritize fixing the error

Format your response as:
RESPONSE: [Your helpful response here, referencing previous outputs if relevant]
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
            
            # Add recent conversation history (last 20 messages to include more command outputs)
            recent_history = self.conversation_history[-20:] if len(self.conversation_history) > 20 else self.conversation_history
            
            conversation_context = system_prompt + "\n\nConversation History:\n"
            for msg in recent_history:
                role = msg['role'].upper()
                content = msg['content']
                
                # Format system messages (command outputs) more clearly
                if msg['role'] == 'system':
                    if content.startswith('Executed command:'):
                        conversation_context += f"EXECUTED: {content.replace('Executed command: ', '')}\n"
                    elif content.startswith('Command output:'):
                        conversation_context += f"OUTPUT: {content.replace('Command output: ', '')}\n"
                    else:
                        conversation_context += f"SYSTEM: {content}\n"
                else:
                    conversation_context += f"{role}: {content}\n"
            
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
                
                # Check if this is an error that can be auto-fixed
                if result.returncode != 0 and (result.stderr or "error" in result.stdout.lower()):
                    print(f"\n🚨 Command failed with return code {result.returncode}")
                    
                    # Try to get a fix suggestion
                    error_output = result.stderr if result.stderr else result.stdout
                    fix_suggestion = self._analyze_command_output_for_errors(command, error_output)
                    
                    # If no pattern-based fix, try AI-powered fix
                    if not fix_suggestion:
                        print("🤖 Analyzing error for potential fix...")
                        fix_suggestion = self._get_error_fix_suggestion(command, output)
                    
                    if fix_suggestion:
                        print(f"💡 Suggested fix command:")
                        print(f"🔧 {fix_suggestion}")
                        
                        choice = self._get_user_choice("❓ Apply this fix? (y/n): ")
                        if choice == 'y':
                            print(f"\n🔧 Applying fix: {fix_suggestion}")
                            fix_result = subprocess.run(
                                fix_suggestion,
                                shell=True,
                                capture_output=True,
                                text=True,
                                cwd=self.current_context['working_directory']
                            )
                            
                            fix_output = ""
                            if fix_result.stdout:
                                fix_output += f"FIX STDOUT:\n{fix_result.stdout}\n"
                            if fix_result.stderr:
                                fix_output += f"FIX STDERR:\n{fix_result.stderr}\n"
                            
                            if fix_result.returncode == 0:
                                print("✅ Fix applied successfully!")
                                
                                # Ask if user wants to retry the original command
                                retry_choice = self._get_user_choice("🔄 Retry the original command? (y/n): ")
                                if retry_choice == 'y':
                                    print(f"\n🔧 Retrying: {command}")
                                    retry_result = subprocess.run(
                                        command,
                                        shell=True,
                                        capture_output=True,
                                        text=True,
                                        cwd=self.current_context['working_directory']
                                    )
                                    
                                    retry_output = ""
                                    if retry_result.stdout:
                                        retry_output += f"RETRY STDOUT:\n{retry_result.stdout}\n"
                                    if retry_result.stderr:
                                        retry_output += f"RETRY STDERR:\n{retry_result.stderr}\n"
                                    if retry_result.returncode != 0:
                                        retry_output += f"RETRY Return code: {retry_result.returncode}\n"
                                    
                                    output += f"\n--- AFTER FIX ---\n{fix_output}\n--- RETRY RESULT ---\n{retry_output}"
                                else:
                                    output += f"\n--- FIX APPLIED ---\n{fix_output}"
                            else:
                                print(f"❌ Fix failed with return code {fix_result.returncode}")
                                output += f"\n--- FIX ATTEMPT FAILED ---\n{fix_output}"
                        else:
                            print("❌ Fix declined.")
                
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
        # Clear screen for dramatic effect
        os.system('clear' if os.name == 'posix' else 'cls')
        
        # Main banner with gradient-like colors
        banner_lines = [
            "\033[38;5;196m" + "  ██╗  ██╗ █████╗  ██████╗██╗  ██╗" + "\033[0m",
            "\033[38;5;202m" + "  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝" + "\033[0m", 
            "\033[38;5;208m" + "  ███████║███████║██║     █████╔╝" + "\033[0m",
            "\033[38;5;214m" + "  ██╔══██║██╔══██║██║     ██╔═██╗" + "\033[0m",
            "\033[38;5;220m" + "  ██║  ██║██║  ██║╚██████╗██║  ██╗" + "\033[0m",
            "\033[38;5;226m" + "  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝" + "\033[0m",
            "",
            "\033[38;5;46m" + "   █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗" + "\033[0m",
            "\033[38;5;82m" + "  ██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝" + "\033[0m",
            "\033[38;5;118m" + "  ███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   " + "\033[0m",
            "\033[38;5;154m" + "  ██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   " + "\033[0m",
            "\033[38;5;190m" + "  ██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║   " + "\033[0m",
            "\033[38;5;226m" + "  ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   " + "\033[0m"
        ]
        
        # Print top border
        print("\033[38;5;51m" + "╔" + "═" * 78 + "╗" + "\033[0m")
        print("\033[38;5;51m" + "║" + " " * 78 + "║" + "\033[0m")
        
        # Print banner lines centered
        for line in banner_lines:
            # Remove ANSI codes to calculate actual text length
            import re
            clean_line = re.sub(r'\033\[[0-9;]*m', '', line)
            padding = (78 - len(clean_line)) // 2
            print("\033[38;5;51m║\033[0m" + " " * padding + line + " " * (78 - padding - len(clean_line)) + "\033[38;5;51m║\033[0m")
        
        # Middle section with effects
        print("\033[38;5;51m" + "║" + " " * 78 + "║" + "\033[0m")
        
        # Subtitle and features with animated-style text
        features = [
            "\033[1;38;5;201m🔥 ELITE HACKER AI ASSISTANT 🔥\033[0m",
            "\033[1;38;5;129m🤖 Powered by Google Gemini 2.0 🤖\033[0m",
            "",
            "\033[38;5;46m[⚡] \033[1;37mPenetration Testing & Security Research\033[0m \033[38;5;46m[⚡]\033[0m",
            "\033[38;5;196m[🛡️ ] \033[1;37mSystem Administration & DevOps\033[0m \033[38;5;196m[🛡️ ]\033[0m", 
            "\033[38;5;75m[💻] \033[1;37mDevelopment & Automation Tasks\033[0m \033[38;5;75m[💻]\033[0m",
            "\033[38;5;226m[🧠] \033[1;37mIntelligent Command Suggestions\033[0m \033[38;5;226m[🧠]\033[0m",
            "\033[38;5;135m[🎯] \033[1;37mContext-Aware AI Responses\033[0m \033[38;5;135m[🎯]\033[0m"
        ]
        
        for feature in features:
            # Calculate padding for centering
            clean_feature = re.sub(r'\033\[[0-9;]*m', '', feature)
            padding = (78 - len(clean_feature)) // 2
            print("\033[38;5;51m║\033[0m" + " " * padding + feature + " " * (78 - padding - len(clean_feature)) + "\033[38;5;51m║\033[0m")
        
        # Bottom border
        print("\033[38;5;51m" + "║" + " " * 78 + "║" + "\033[0m")
        print("\033[38;5;51m" + "╚" + "═" * 78 + "╝" + "\033[0m")
        
        # Warning with blinking effect
        print("\n" + "\033[1;5;91m🚨 WARNING: FOR AUTHORIZED PENETRATION TESTING & RESEARCH ONLY! 🚨\033[0m")
        print("\033[1;93m⚖️  Always obtain proper authorization before security testing! ⚖️\033[0m\n")

    def _analyze_command_output_for_errors(self, command: str, output: str) -> Optional[str]:
        """Analyze command output for common errors and suggest fixes."""
        output_lower = output.lower()
        
        # Common error patterns and their fixes
        error_fixes = {
            "permission denied": f"sudo {command}",
            "command not found": None,  # Will be handled specially
            "no such file or directory": f"ls -la && {command}",
            "connection refused": "Check if the service is running or firewall settings",
            "network unreachable": "Check network connectivity with: ping 8.8.8.8",
            "port already in use": "Check what's using the port with: netstat -tulnp",
            "disk space": "Check disk usage with: df -h",
            "memory": "Check memory usage with: free -h",
            "syntax error": "Review the command syntax",
            "access denied": f"sudo {command}",
            "authentication failed": "Check credentials or permissions"
        }
        
        # Check for command not found specifically
        if "command not found" in output_lower:
            cmd_name = command.split()[0] if command.split() else ""
            if cmd_name:
                return f"apt-get update && apt-get install -y {cmd_name}"
        
        # Check for other error patterns
        for error_pattern, fix in error_fixes.items():
            if error_pattern in output_lower and fix:
                return fix
                
        return None

    def _get_error_fix_suggestion(self, command: str, output: str) -> Optional[str]:
        """Get AI-powered error fix suggestion."""
        try:
            error_prompt = f"""The command '{command}' failed with this output:
{output}

Please provide a specific Linux command to fix this error. Respond in format:
RESPONSE: Brief explanation of the error
COMMAND: Single command to fix the issue, or NONE if cannot be fixed automatically"""

            # Get AI response for error fixing
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=error_prompt
            )
            ai_response = response.text.strip()
            
            # Parse the response for suggested fix command
            lines = ai_response.split('\n')
            for line in lines:
                if line.startswith('COMMAND:'):
                    cmd = line.replace('COMMAND:', '').strip()
                    if cmd and cmd.upper() != 'NONE':
                        return cmd
            return None
            
        except Exception:
            return None

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
