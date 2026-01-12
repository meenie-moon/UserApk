import asyncio
import os
import time
import json
import re
from telethon.sync import TelegramClient
from telethon import errors, functions, types

# --- Rich UI Imports ---
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint

console = Console()

# --- Storage Constants ---
CREDENTIALS_FILE = "credentials.txt" # Legacy support
ACCOUNTS_FILE = "accounts.json"
TEMPLATE_FILE = "target_templates.json"

# --- UI Helpers ---

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    banner_text = Text(r"""
  __  __                  _______   _      
 |  \/  |                |__   __| | |     
 | \  / | ___   ___  _ __   | | ___| | ___ 
 | |\/| |/ _ \ / _ \| '_ \  | |/ _ \ |/ _ \
 | |  | | (_) | (_) | | | | | |  __/ |  __/
 |_|  |_|\___/ \___/|_| |_| |_|\___|_|\___|
                                           
      Telegram Broadcast CLI (Lite)
""", style="bold cyan")
    console.print(Panel(banner_text, border_style="blue", expand=False))

# --- Core Logic ---

class TelegramForwarder:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('session_' + phone_number, api_id, api_hash)

    async def _ensure_authorized(self):
        """Handle connection and login."""
        await self.client.connect()
        if not await self.client.is_user_authorized():
            try:
                await self.client.send_code_request(self.phone_number)
                code = input('Enter the code you received: ')
                await self.client.sign_in(self.phone_number, code)
            except errors.rpcerrorlist.SessionPasswordNeededError:
                password = input('Two-step verification is enabled. Enter your password: ')
                await self.client.sign_in(password=password)

    async def resolve_target_from_input(self, input_str):
        """
        Detects if input is User ID or Link, validates it, and returns target info.
        Returns: dict or None
        """
        await self._ensure_authorized()
        input_str = input_str.strip()
        
        target_info = {
            "chat_id": None,
            "chat_title": None,
            "topic_id": None,
            "topic_title": None,
            "type": "Unknown"
        }

        try:
            # 1. Check if input is purely numeric (User ID)
            if input_str.isdigit() or (input_str.startswith("-") and input_str[1:].isdigit()):
                user_id = int(input_str)
                entity = await self.client.get_entity(user_id)
                target_info["chat_id"] = entity.id
                target_info["chat_title"] = f"{entity.first_name} {entity.last_name or ''}".strip() if hasattr(entity, 'first_name') else (entity.title if hasattr(entity, 'title') else "Unknown")
                target_info["type"] = "User/Chat"
                return target_info

            # 2. Check if input is a Link
            elif "t.me/" in input_str:
                # Remove protocol and standard clean up
                clean_link = input_str.replace("https://", "").replace("http://", "").replace("t.me/", "")
                parts = clean_link.split("/")
                
                chat_identifier = None
                msg_id = None
                topic_id_from_url = None

                # Handle Private Link /c/
                if parts[0] == "c":
                    # format: c/CHAT_ID/MSG_ID or c/CHAT_ID/TOPIC_ID/MSG_ID
                    if len(parts) >= 3:
                        chat_identifier = int(f"-100{parts[1]}") # Add -100 prefix for private supergroups
                        msg_id = int(parts[-1].split("?")[0])
                        
                        # If there are 4 parts (c/id/topic/msg), grab topic
                        if len(parts) == 4:
                            topic_id_from_url = int(parts[2])
                else:
                    # format: username/MSG_ID or username/topic/MSG_ID (rare)
                    chat_identifier = parts[0]
                    if len(parts) > 1:
                        msg_id = int(parts[-1].split("?")[0])

                if not chat_identifier:
                    console.print("[red]❌ Could not parse link format.[/red]")
                    return None

                # Fetch Message to Validate and get details
                console.print(f"[dim]🔄 Verifying access to {chat_identifier}...[/dim]")
                
                try:
                    # Get Chat Entity
                    entity = await self.client.get_entity(chat_identifier)
                    target_info["chat_id"] = entity.id
                    target_info["chat_title"] = entity.title if hasattr(entity, 'title') else (entity.username or "Unknown")
                    target_info["type"] = "Group/Channel"

                    # If valid message ID exists, use it to detect topic
                    if msg_id:
                        message = await self.client.get_messages(entity, ids=msg_id)
                        if message:
                            # Check for Topic info in message
                            if message.reply_to and message.reply_to.forum_topic:
                                target_info["topic_id"] = message.reply_to.reply_to_msg_id
                            elif message.reply_to and message.reply_to.reply_to_msg_id:
                                # Sometimes in forums, reply_to points to the thread start
                                # We might want to assume it's the topic if the group is a forum
                                if getattr(entity, 'forum', False):
                                    target_info["topic_id"] = message.reply_to.reply_to_msg_id
                            
                            # Override if URL specifically had topic (stronger signal for private links)
                            if topic_id_from_url:
                                target_info["topic_id"] = topic_id_from_url

                    # If we found a topic ID, try to get its title
                    if target_info["topic_id"]:
                        try:
                            # Attempt to fetch topic info (thread start message)
                            # In forums, the topic ID is usually the ID of the first message
                            topic_start_msg = await self.client.get_messages(entity, ids=target_info["topic_id"])
                            if topic_start_msg:
                                # Try to find a title (forum topics usually have action message or text)
                                if hasattr(topic_start_msg, 'action') and hasattr(topic_start_msg.action, 'title'):
                                    target_info["topic_title"] = topic_start_msg.action.title
                                else:
                                    target_info["topic_title"] = topic_start_msg.text[:30] if topic_start_msg.text else f"Topic {target_info['topic_id']}"
                        except:
                            target_info["topic_title"] = f"Topic {target_info['topic_id']}"

                    return target_info

                except Exception as e:
                    console.print(f"[red]❌ Error resolving link: {e}[/red]")
                    return None

            else:
                console.print("[red]❌ Invalid input. Must be a t.me Link or Numeric User ID.[/red]")
                return None

        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return None

    async def send_custom_message(self, chat_id, text, topic_id=None, chat_title="Unknown", topic_title=None):
        await self._ensure_authorized()
        try:
            await self.client.send_message(chat_id, text, reply_to=topic_id)
            target_info = f"{chat_title}" + (f" (Topic: {topic_title})" if topic_title else "")
            print(f"✅ Sent to: {target_info}")
            return True
        except Exception as e:
            print(f"❌ Failed to send to {chat_title}: {e}")
            return False

    async def forward_existing_message(self, target_chat_id, message_object, topic_id=None, chat_title="Unknown", topic_title=None, as_forward=False):
        await self._ensure_authorized()
        try:
            if as_forward:
                # True Forward
                if isinstance(message_object, list):
                    msg_ids = [m.id for m in message_object]
                    origin_chat_id = message_object[0].chat_id
                else:
                    msg_ids = [message_object.id]
                    origin_chat_id = message_object.chat_id

                from_peer = await self.client.get_input_entity(origin_chat_id)
                target_peer = await self.client.get_input_entity(target_chat_id)

                await self.client(functions.messages.ForwardMessagesRequest(
                    from_peer=from_peer,
                    id=msg_ids,
                    to_peer=target_peer,
                    top_msg_id=topic_id if topic_id else None
                ))
            else:
                # Send as Copy (Album support)
                if isinstance(message_object, list):
                    caption = None
                    for m in message_object:
                        if m.text:
                            caption = m.text
                            break
                    await self.client.send_message(
                        target_chat_id, 
                        message=caption, 
                        file=message_object, 
                        reply_to=topic_id
                    )
                else:
                    await self.client.send_message(target_chat_id, message_object, reply_to=topic_id)
                
            target_info = f"{chat_title}" + (f" (Topic: {topic_title})" if topic_title else "")
            mode_str = "Forwarded" if as_forward else "Sent Copy"
            print(f"✅ {mode_str} to: {target_info}")
            return True
        except Exception as e:
            print(f"❌ Failed to process {chat_title}: {e}")
            return False

# --- Account & Template Managers ---

def load_accounts():
    accounts = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
        except: pass
    
    # Migration from credentials.txt
    if not accounts and os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as file:
                lines = file.readlines()
                if len(lines) >= 3:
                    accounts.append({
                        "phone": lines[2].strip(),
                        "api_id": lines[0].strip(),
                        "api_hash": lines[1].strip(),
                        "name": f"Account {lines[2].strip()}"
                    })
                    save_accounts(accounts)
        except: pass
    return accounts

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=4)

def add_account_interactive(accounts):
    print("\n=== ADD NEW ACCOUNT ===")
    api_id = input("API ID: ").strip()
    api_hash = input("API Hash: ").strip()
    phone = input("Phone Number: ").strip()
    name = input("Label (e.g. My Personal): ").strip() or f"Account {phone}"
    
    accounts.append({"phone": phone, "api_id": api_id, "api_hash": api_hash, "name": name})
    save_accounts(accounts)
    print(f"✅ Account '{name}' added!")
    return accounts

def load_templates(account_phone):
    if not os.path.exists(TEMPLATE_FILE): return {}
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Legacy migration check
        if data and isinstance(next(iter(data.values())), list):
            # Migrate flat structure to per-phone structure
            data = {account_phone: data}
            with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        
        return data.get(account_phone, {})
    except: return {}

def save_templates(current_account_templates, account_phone):
    full_data = {}
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if content and not isinstance(next(iter(content.values())), list):
                    full_data = content
        except: pass
    
    full_data[account_phone] = current_account_templates
    with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(full_data, f, indent=4, ensure_ascii=False)

# --- Menus ---

async def manage_templates(forwarder, account_phone):
    while True:
        templates = load_templates(account_phone)
        print_banner()
        console.print(f"[bold cyan]📁 MANAGE TARGETS & TEMPLATES ({account_phone})[/bold cyan]\n")
        
        console.print(Panel("[1] View Templates       [2] Create New Template\n[3] Edit Template        [4] Delete Template\n[5] Back to Main Menu", title="Actions", border_style="blue"))
        
        choice = console.input("[bold yellow]❯ Enter choice: [/bold yellow]")
        
        if choice == "1":
            if not templates:
                console.print("[yellow]⚠️ No templates found.[/yellow]")
                time.sleep(1)
                continue
            
            table = Table(title="Available Templates", box=None)
            table.add_column("No", style="cyan", justify="right")
            table.add_column("Name", style="white")
            table.add_column("Targets", style="green")
            keys = list(templates.keys())
            for i, key in enumerate(keys, 1):
                table.add_row(str(i), key, str(len(templates[key])))
            console.print(table)
            
            try:
                sel = console.input("\n[bold yellow]❯ Enter number to view details (or press Enter to back): [/bold yellow]")
                if sel.isdigit():
                    idx = int(sel) - 1
                    if 0 <= idx < len(keys):
                        t_name = keys[idx]
                        targets = templates[t_name]
                        
                        detail_table = Table(title=f"Detailed Targets: {t_name}", border_style="cyan")
                        detail_table.add_column("No", justify="right")
                        detail_table.add_column("Target Name", style="white")
                        detail_table.add_column("Type", style="dim")
                        detail_table.add_column("Topic", style="yellow")
                        
                        for j, target in enumerate(targets, 1):
                            detail_table.add_row(
                                str(j), 
                                str(target.get('chat_title', 'Unknown')),
                                str(target.get('type', 'Group')),
                                str(target.get('topic_title') or "-")
                            )
                        console.print(detail_table)
                        console.input("\n[dim]Press Enter to continue...[/dim]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                time.sleep(1)

        elif choice == "2":
            name = console.input("Enter new template name: ").strip()
            if not name: continue
            if name in templates:
                if not Confirm.ask("Template exists. Overwrite?"): continue
            
            new_targets = []
            console.print(Panel("[bold]Cara Menambahkan Target:[/bold]\n1. Untuk [cyan]Grup/Channel/Forum[/cyan]: Kirim Link Pesan (contoh: https://t.me/grup/123)\n2. Untuk [cyan]User[/cyan]: Kirim User ID (angka)", border_style="green"))
            
            while True:
                user_input = console.input(f"[bold yellow]❯ Paste Link/ID (Target #{len(new_targets)+1}) or 'done': [/bold yellow]")
                if user_input.lower() == 'done': break
                if not user_input.strip(): continue

                with console.status("Resolving target...", spinner="dots"):
                    target = await forwarder.resolve_target_from_input(user_input)
                
                if target:
                    # Check duplicate in current session
                    if any(t['chat_id'] == target['chat_id'] and t['topic_id'] == target['topic_id'] for t in new_targets):
                        console.print("[yellow]⚠️ Target already in list.[/yellow]")
                    else:
                        new_targets.append(target)
                        desc = f"{target['chat_title']}"
                        if target['topic_title']: desc += f" > {target['topic_title']}"
                        console.print(f"[green]✅ Added: {desc}[/green]")
                
            if new_targets:
                templates[name] = new_targets
                save_templates(templates, account_phone)
                console.print(f"[green]💾 Template '{name}' saved with {len(new_targets)} targets.[/green]")
                asyncio.sleep(1)

        elif choice == "3":
            if not templates: continue
            keys = list(templates.keys())
            for i, key in enumerate(keys, 1): console.print(f"{i}. {key}")
            try:
                idx = int(console.input("Select template: ")) - 1
                if 0 <= idx < len(keys):
                    t_name = keys[idx]
                    current = templates[t_name]
                    
                    console.print("[1] Add Target  [2] Remove Target")
                    if console.input("Action: ") == "1":
                        user_input = console.input("[bold yellow]❯ Paste Link/ID: [/bold yellow]")
                        with console.status("Resolving..."):
                            target = await forwarder.resolve_target_from_input(user_input)
                        if target:
                            current.append(target)
                            save_templates(templates, account_phone)
                            console.print("[green]✅ Added.[/green]")
                    else:
                        for i, t in enumerate(current, 1): 
                            console.print(f"{i}. {t['chat_title']} {f'({t['topic_title']})' if t['topic_title'] else ''}")
                        rm_idx = int(console.input("Remove number: ")) - 1
                        if 0 <= rm_idx < len(current):
                            current.pop(rm_idx)
                            save_templates(templates, account_phone)
                            console.print("[green]🗑️ Removed.[/green]")
            except: pass

        elif choice == "4":
            keys = list(templates.keys())
            for i, k in enumerate(keys, 1): console.print(f"{i}. {k}")
            try:
                idx = int(console.input("Delete number: ")) - 1
                if 0 <= idx < len(keys) and Confirm.ask("Are you sure?"):
                    del templates[keys[idx]]
                    save_templates(templates, account_phone)
                    console.print("[green]🗑️ Deleted.[/green]")
            except: pass

        elif choice == "5":
            break
        
        time.sleep(1)

async def main():
    print("\n=== Telegram Automation (Lite) ===\n")
    accounts = load_accounts()
    if not accounts:
        accounts = add_account_interactive(accounts)
        if not accounts: return

    active_account = accounts[0]
    
    while True:
        print(f"\n🔑 Logging in as: {active_account['name']}...")
        forwarder = TelegramForwarder(active_account['api_id'], active_account['api_hash'], active_account['phone'])
        
        try:
            await forwarder._ensure_authorized()
            me = await forwarder.client.get_me()
            tg_name = f"{me.first_name} {me.last_name or ''}".strip()
            if me.username:
                tg_name += f" (@{me.username})"
            active_account['real_name'] = tg_name
            save_accounts(accounts)
        except Exception as e:
            print(f"❌ Login failed: {e}")
            retry = input("Manage accounts? (y/n): ")
            if retry.lower() == 'y':
                # Simple jump to account management logic
                pass
            return

        while True:
            print_banner()
            
            # Main Menu
            menu = Table(show_header=False, box=None)
            menu.add_column("Key", style="cyan bold", justify="right")
            menu.add_column("Desc")
            
            menu.add_row("[1]", "📝 Manage Target Templates")
            menu.add_row("[2]", "🚀 Send Message / Broadcast")
            menu.add_row("[3]", "👥 Manage Accounts")
            menu.add_row("[4]", "🚪 Exit")
            
            console.print(Panel(Text(f"Active: {tg_name} ({active_account['phone']})", style="green"), title="Status"))
            console.print(menu)
            
            choice = console.input("[bold yellow]❯ Choice: [/bold yellow]")
            
            if choice == "1":
                await manage_templates(forwarder, active_account['phone'])
            
            elif choice == "2":
                templates = load_templates(active_account['phone'])
                if not templates:
                    console.print("[yellow]⚠️ You have no templates. Go to menu [1] first.[/yellow]")
                    import time; time.sleep(2)
                    continue

                console.print("\n[bold cyan]🚀 BROADCAST MODE[/bold cyan]")
                keys = list(templates.keys())
                for i, k in enumerate(keys, 1):
                    console.print(f"{i}. {k} ({len(templates[k])} targets)")
                
                try:
                    t_idx_input = console.input("Select Template Number: ")
                    if not t_idx_input.isdigit(): continue
                    t_idx = int(t_idx_input) - 1
                    
                    if not (0 <= t_idx < len(keys)): continue
                    
                    selected_template = templates[keys[t_idx]]
                    targets = selected_template # List of {chat_id, topic_id...}
                    
                    console.print(Panel("[1] Manual Text Input\n[2] Forward Existing Message (Link)", title="Source", border_style="blue"))
                    src_choice = console.input("Select Source: ")
                    
                    message_to_send = None
                    msg_obj = None
                    
                    if src_choice == "1":
                        console.print("Type message (Enter twice to finish):")
                        lines = []
                        while True:
                            l = input()
                            if not l: break
                            lines.append(l)
                        message_to_send = "\n".join(lines)
                        
                    elif src_choice == "2":
                        link = console.input("Paste Message Link: ").strip()
                        if "t.me" in link:
                            # Parse quickly
                            try:
                                clean = link.replace("https://", "").replace("t.me/", "")
                                parts = clean.split("/")
                                mid = int(parts[-1].split("?")[0])
                                cid = parts[-2] if parts[-2] != "c" else int(f"-100{parts[1]}") # Crude parse
                                # Better: re-use resolve logic but we just need object
                                if isinstance(cid, str) and cid == "c":
                                     pass 
                                
                                # For safety, let's just ask the client to fetch based on simple parse
                                # If private link with /c/: t.me/c/1234/99
                                if "/c/" in link:
                                    c_idx = link.find("/c/")
                                    sub = link[c_idx+3:]
                                    p = sub.split("/")
                                    cid = int(f"-100{p[0]}")
                                    mid = int(p[-1])
                                else:
                                    # public
                                    p = clean.split("/")
                                    cid = p[0]
                                    mid = int(p[-1])
                                    
                                msg_obj = await forwarder.client.get_messages(cid, ids=mid)
                                if msg_obj:
                                    console.print("[green]✅ Message fetched![/green]")
                            except Exception as e:
                                console.print(f"[red]Error fetching message: {e}[/red]")
                        
                    if message_to_send or msg_obj:
                        delay_input = console.input("Delay (sec) [Default 5]: ")
                        delay = float(delay_input) if delay_input else 5.0
                        
                        if Confirm.ask(f"Start sending to {len(targets)} targets?"):
                            with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
                                task = progress.add_task("Sending...", total=len(targets))
                                for t in targets:
                                    progress.update(task, description=f"Sending to {t['chat_title']}...")
                                    if msg_obj:
                                        await forwarder.forward_existing_message(t['chat_id'], msg_obj, topic_id=t['topic_id'], chat_title=t['chat_title'], topic_title=t['topic_title'])
                                    else:
                                        await forwarder.send_custom_message(t['chat_id'], message_to_send, topic_id=t['topic_id'], chat_title=t['chat_title'], topic_title=t['topic_title'])
                                    progress.advance(task)
                                    await asyncio.sleep(delay)
                            console.print("[green]DONE![/green]")
                            import time; time.sleep(2)
                            
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    import time; time.sleep(2)

            elif choice == "3":
                # Simple Account Switcher
                print_banner()
                console.print("[bold]Manage Accounts[/bold]")
                for i, acc in enumerate(accounts, 1):
                    prefix = "✅ " if acc == active_account else "   "
                    console.print(f"{prefix}{i}. {acc.get('name')} ({acc['phone']})")
                
                console.print("\n[A] Add Account  [D] Delete Account  [S] Switch  [B] Back")
                act = console.input("Choice: ").upper()
                
                if act == "A":
                    accounts = add_account_interactive(accounts)
                elif act == "S":
                    try:
                        idx = int(console.input("Select Number: ")) - 1
                        if 0 <= idx < len(accounts):
                            new_acc = accounts[idx]
                            await forwarder.client.disconnect()
                            active_account = new_acc
                            break # Break inner loop to re-login
                    except: pass
                elif act == "D":
                     try:
                        idx = int(console.input("Delete Number: ")) - 1
                        if 0 <= idx < len(accounts) and accounts[idx] != active_account:
                            accounts.pop(idx)
                            save_accounts(accounts)
                            console.print("Deleted.")
                     except: pass
            
            elif choice == "4":
                await forwarder.client.disconnect()
                return

if __name__ == "__main__":
    asyncio.run(main())
