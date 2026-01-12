import asyncio
import os
import json
import re
from kivy.lang import Builder
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineListItem, ThreeLineListItem, MDList
from kivymd.uix.textfield import MDTextField
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.clock import Clock
from telethon import TelegramClient, errors, functions, types

# Telethon with pyaes for Android compatibility
import pyaes 

# --- Constants ---
ACCOUNTS_FILE_NAME = "accounts.json"
TEMPLATE_FILE_NAME = "target_templates.json"

KV = '''
MDBoxLayout:
    orientation: "vertical"

    MDTopAppBar:
        title: "MoonTele Android"
        elevation: 4
        pos_hint: {"top": 1}
        right_action_items: [["account-multiple", lambda x: app.switch_screen("accounts")], ["folder-sync", lambda x: app.switch_screen("templates")]]

    MDScreenManager:
        id: screen_manager

        MDScreen:
            name: "home"
            MDBoxLayout:
                orientation: "vertical"
                padding: "16dp"
                spacing: "12dp"

                MDLabel:
                    id: status_label
                    text: "Welcome to MoonTele"
                    halign: "center"
                    theme_text_color: "Secondary"
                    font_style: "H6"

                MDLabel:
                    id: active_account_label
                    text: "No account selected"
                    halign: "center"
                    theme_text_color: "Hint"

                MDRaisedButton:
                    text: "🚀 START BROADCAST"
                    pos_hint: {"center_x": .5}
                    on_release: app.switch_screen("broadcast")
                
                Widget:

        MDScreen:
            name: "accounts"
            MDBoxLayout:
                orientation: "vertical"
                padding: "16dp"
                
                MDLabel:
                    text: "Accounts"
                    font_style: "H5"
                    size_hint_y: None
                    height: "40dp"

                ScrollView:
                    MDList:
                        id: account_list

                MDFloatingActionButton:
                    icon: "plus"
                    pos_hint: {"right": 1}
                    on_release: app.show_add_account_dialog()

        MDScreen:
            name: "templates"
            MDBoxLayout:
                orientation: "vertical"
                padding: "16dp"
                
                MDLabel:
                    text: "Target Templates"
                    font_style: "H5"
                    size_hint_y: None
                    height: "40dp"

                ScrollView:
                    MDList:
                        id: template_list

                MDFloatingActionButton:
                    icon: "plus"
                    pos_hint: {"right": 1}
                    on_release: app.show_add_template_dialog()

        MDScreen:
            name: "broadcast"
            MDBoxLayout:
                orientation: "vertical"
                padding: "16dp"
                spacing: "12dp"

                MDLabel:
                    text: "New Broadcast"
                    font_style: "H5"
                    size_hint_y: None
                    height: "40dp"

                MDRaisedButton:
                    id: select_template_btn
                    text: "Select Template"
                    pos_hint: {"center_x": .5}
                    on_release: app.show_template_menu()

                MDTextField:
                    id: broadcast_text
                    hint_text: "Message (Text or Message Link)"
                    multiline: True
                
                MDTextField:
                    id: broadcast_delay
                    hint_text: "Delay (seconds)"
                    text: "5"
                    input_filter: "float"

                MDRaisedButton:
                    text: "SEND"
                    pos_hint: {"center_x": .5}
                    on_release: app.start_broadcast()

                MDProgressBar:
                    id: progress_bar
                    value: 0
                    opacity: 0

                MDLabel:
                    id: progress_label
                    text: ""
                    halign: "center"
'''

class MoonTeleApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.accounts = []
        self.templates = {}
        self.active_account = None
        self.client = None
        self.dialog = None

    def build(self):
        self.theme_cls.primary_palette = "Cyan"
        self.theme_cls.theme_style = "Dark"
        self.data_dir = self.user_data_dir
        return Builder.load_string(KV)

    def on_start(self):
        self.load_data()
        self.refresh_account_list()
        self.refresh_template_list()

    def load_data(self):
        acc_path = os.path.join(self.data_dir, ACCOUNTS_FILE_NAME)
        tpl_path = os.path.join(self.data_dir, TEMPLATE_FILE_NAME)
        if os.path.exists(acc_path):
            try:
                with open(acc_path, 'r') as f:
                    self.accounts = json.load(f)
            except: pass
        if os.path.exists(tpl_path):
            try:
                with open(tpl_path, 'r') as f:
                    self.templates = json.load(f)
            except: pass

    def save_data(self):
        acc_path = os.path.join(self.data_dir, ACCOUNTS_FILE_NAME)
        tpl_path = os.path.join(self.data_dir, TEMPLATE_FILE_NAME)
        with open(acc_path, 'w') as f:
            json.dump(self.accounts, f, indent=4)
        with open(tpl_path, 'w') as f:
            json.dump(self.templates, f, indent=4)

    def switch_screen(self, screen_name):
        self.root.ids.screen_manager.current = screen_name

    def refresh_account_list(self):
        self.root.ids.account_list.clear_widgets()
        for acc in self.accounts:
            item = ThreeLineListItem(
                text=acc.get('name', 'Unnamed'),
                secondary_text=acc.get('phone', ''),
                tertiary_text="Active" if self.active_account == acc else "",
                on_release=lambda x, a=acc: self.select_account(a)
            )
            self.root.ids.account_list.add_widget(item)

    def select_account(self, acc):
        self.active_account = acc
        self.root.ids.active_account_label.text = f"Active: {acc['name']} ({acc['phone']})"
        self.refresh_account_list()
        self.switch_screen("home")
        asyncio.create_task(self.init_client(acc))

    async def init_client(self, acc):
        session_path = os.path.join(self.data_dir, f"session_{acc['phone']}")
        self.client = TelegramClient(session_path, int(acc['api_id']), acc['api_hash'])
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                self.show_auth_dialog(acc['phone'])
            else:
                me = await self.client.get_me()
                self.root.ids.status_label.text = f"Logged in as {me.first_name}"
        except Exception as e:
            Snackbar(text=f"Connection error: {str(e)}").open()

    def show_auth_dialog(self, phone):
        content = MDTextField(hint_text="Enter Code")
        self.dialog = MDDialog(
            title="Authentication",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SUBMIT", on_release=lambda x: self.finish_auth(phone, content.text))
            ]
        )
        self.dialog.open()

    def finish_auth(self, phone, code):
        self.dialog.dismiss()
        asyncio.create_task(self._finish_auth(phone, code))

    async def _finish_auth(self, phone, code):
        try:
            await self.client.sign_in(phone, code)
            me = await self.client.get_me()
            self.root.ids.status_label.text = f"Logged in as {me.first_name}"
        except Exception as e:
            Snackbar(text=f"Auth error: {str(e)}").open()

    def show_add_account_dialog(self):
        layout = MDBoxLayout(orientation="vertical", spacing="12dp", size_hint_y=None, height="300dp")
        name = MDTextField(hint_text="Account Label")
        api_id = MDTextField(hint_text="API ID")
        api_hash = MDTextField(hint_text="API Hash")
        phone = MDTextField(hint_text="Phone (with +)")
        layout.add_widget(name)
        layout.add_widget(api_id)
        layout.add_widget(api_hash)
        layout.add_widget(phone)

        self.dialog = MDDialog(
            title="Add Account",
            type="custom",
            content_cls=layout,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", on_release=lambda x: self.add_account(name.text, api_id.text, api_hash.text, phone.text))
            ]
        )
        self.dialog.open()

    def add_account(self, name, api_id, api_hash, phone):
        self.accounts.append({"name": name, "api_id": api_id, "api_hash": api_hash, "phone": phone})
        self.save_data()
        self.refresh_account_list()
        self.dialog.dismiss()

    def refresh_template_list(self):
        self.root.ids.template_list.clear_widgets()
        acc_phone = self.active_account['phone'] if self.active_account else "default"
        acc_templates = self.templates.get(acc_phone, {})
        for name, targets in acc_templates.items():
            item = OneLineListItem(
                text=f"{name} ({len(targets)} targets)",
                on_release=lambda x, n=name: self.show_template_details(n)
            )
            self.root.ids.template_list.add_widget(item)

    def show_add_template_dialog(self):
        if not self.active_account:
            Snackbar(text="Select an account first").open()
            return
        
        name = MDTextField(hint_text="Template Name")
        self.dialog = MDDialog(
            title="New Template",
            type="custom",
            content_cls=name,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="CREATE", on_release=lambda x: self.create_template(name.text))
            ]
        )
        self.dialog.open()

    def create_template(self, name):
        acc_phone = self.active_account['phone']
        if acc_phone not in self.templates:
            self.templates[acc_phone] = {}
        self.templates[acc_phone][name] = []
        self.save_data()
        self.refresh_template_list()
        self.dialog.dismiss()
        self.show_template_details(name)

    def show_template_details(self, name):
        self.dialog = MDDialog(
            title=f"Template: {name}",
            text="Add targets via link or ID.",
            buttons=[
                MDFlatButton(text="CLOSE", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="ADD TARGET", on_release=lambda x: self.show_add_target_dialog(name))
            ]
        )
        self.dialog.open()

    def show_add_target_dialog(self, template_name):
        target_input = MDTextField(hint_text="Link or ID")
        self.dialog.dismiss()
        self.dialog = MDDialog(
            title="Add Target",
            type="custom",
            content_cls=target_input,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="RESOLVE", on_release=lambda x: self.resolve_and_add_target(template_name, target_input.text))
            ]
        )
        self.dialog.open()

    def resolve_and_add_target(self, template_name, input_str):
        self.dialog.dismiss()
        asyncio.create_task(self._resolve_target(template_name, input_str))

    async def _resolve_target(self, template_name, input_str):
        if not self.client: return
        try:
            target_info = await self.resolve_logic(input_str)
            if target_info:
                acc_phone = self.active_account['phone']
                self.templates[acc_phone][template_name].append(target_info)
                self.save_data()
                self.refresh_template_list()
                Snackbar(text=f"Added {target_info['chat_title']}").open()
        except Exception as e:
            Snackbar(text=f"Error: {str(e)}").open()

    async def resolve_logic(self, input_str):
        input_str = input_str.strip()
        target_info = {"chat_id": None, "chat_title": None, "topic_id": None, "topic_title": None, "type": "Unknown"}
        try:
            if input_str.isdigit() or (input_str.startswith("-") and input_str[1:].isdigit()):
                user_id = int(input_str)
                entity = await self.client.get_entity(user_id)
                target_info["chat_id"] = entity.id
                target_info["chat_title"] = getattr(entity, 'title', 'User')
                target_info["type"] = "User"
                return target_info
            elif "t.me/" in input_str:
                entity = await self.client.get_entity(input_str)
                target_info["chat_id"] = entity.id
                target_info["chat_title"] = getattr(entity, 'title', 'Group')
                target_info["type"] = "Group"
                return target_info
        except Exception as e:
            print(f"Error resolving: {e}")
        return None

    def show_template_menu(self):
        if not self.active_account: return
        acc_templates = self.templates.get(self.active_account['phone'], {})
        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": name,
                "on_release": lambda x=name: self.set_broadcast_template(x),
            } for name in acc_templates.keys()
        ]
        self.menu = MDDropdownMenu(
            caller=self.root.ids.select_template_btn,
            items=menu_items,
            width_mult=4,
        )
        self.menu.open()

    def set_broadcast_template(self, name):
        self.root.ids.select_template_btn.text = name
        self.menu.dismiss()

    def start_broadcast(self):
        template_name = self.root.ids.select_template_btn.text
        if template_name == "Select Template":
            Snackbar(text="Please select a template").open()
            return
        text = self.root.ids.broadcast_text.text
        if not text:
            Snackbar(text="Message cannot be empty").open()
            return
        delay = float(self.root.ids.broadcast_delay.text or 5)
        asyncio.create_task(self._run_broadcast(template_name, text, delay))

    async def _run_broadcast(self, template_name, text, delay):
        acc_phone = self.active_account['phone']
        targets = self.templates[acc_phone][template_name]
        self.root.ids.progress_bar.opacity = 1
        self.root.ids.progress_bar.max = len(targets)
        count = 0
        for t in targets:
            self.root.ids.progress_label.text = f"Sending to {t['chat_title']}..."
            try:
                await self.client.send_message(t['chat_id'], text, reply_to=t['topic_id'])
                count += 1
            except Exception as e:
                print(f"Failed: {e}")
            self.root.ids.progress_bar.value = count
            await asyncio.sleep(delay)
        self.root.ids.progress_label.text = f"Finished! Sent to {count}/{len(targets)} targets."
        self.root.ids.progress_bar.opacity = 0
        Snackbar(text="Broadcast Complete").open()

if __name__ == "__main__":
    app = MoonTeleApp()
    asyncio.run(app.async_run())