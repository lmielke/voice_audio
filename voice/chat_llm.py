import ast, json, os, re, subprocess, sys, threading, time, urllib.error, urllib.request
from tabulate import tabulate as tb
from voice_class import App, Conversation
from colorama import Fore, Back, Style


class Assistant:
    
    def __init__(self, altered_cwd: str = "") -> None:
        """
        Initialize the Assistant with the working directory for the external
        command. Defaults to os.environ["altered_bytes"] if not provided.
        """
        self.altered_cwd = altered_cwd or os.environ.get("altered_bytes", ".")
        self.response_string = "Voice Assistant: "

    def get_response(self, user_prompt: str) -> tuple:
        """
        Get processed assistant response for a given user prompt.
        """
        payload = self._prep_payload(user_prompt)
        r = self._send_request(payload)
        return self.process_altered_result(r)


    def _prep_payload(self, user_prompt: str) -> dict:
        """
        Prepare payload for the FastAPI server call.
        """
        switch, user_prompt = self.prep_device_payload(user_prompt)
        print(f"{Fore.CYAN}\nAssistant._prep_payload:{Fore.RESET} {switch = }\n{user_prompt = }")
        return {
            "api_name": 'tool_call' if switch else 'thought',
            "application": self.response_string,
            "user_prompt": user_prompt,
            "tool_choice": "toggle_device" if switch else None,
            "verbose": 0,
            "alias": "qwq_0"
        }

    def prep_device_payload(self, user_prompt:str) -> dict:
        switch = 'switch' in user_prompt
        status = 'status' in user_prompt
        if switch or status:
            # Add a sleep to ensure the API has time to process the request
            device_status = self.get_devices()
            user_prompt += (    f"\n<system>"
                                f"\nHere are names and status of all available devices:"
                                f"\nCheck the device status and only toggle it if needed."
                                f"\n{device_status = }"
                                f"\n</system>\n"
                                )
        return switch, user_prompt

    def _send_request(self, payload: dict) -> str:
        """
        Send request to the FastAPI server and return raw response string.
        """
        IP, PORT = json.loads(os.environ['ALTERED_BYTES_FAST_API']).values()
        url = f"http://{IP}:{PORT}/call/"
        # url = f"http://127.0.0.1:{os.environ.get('ALTERED_BYTES_PORT', 8777)}/call/"
        try:
            data = json.dumps(payload).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as response:
                r = response.read().decode('utf-8')
                return json.loads(r.split(self.response_string)[-1].strip())
        except Exception as e:
            print(f"{Fore.RED}ERROR: chat_llm.Assistant._send_request:{Fore.RESET} {e}")
            return {"response": f"ERROR {e = }"}


    def process_altered_result(self, r: str) -> tuple:
        """
        Process the result from the altered API response.
        """
        response, answer = r.get("response"), ""
        for marker in {'\n# Answer:', '\n# Answer', '\nAnswer:', '\nAnswer'}:
            if marker in response:
                answer = response.split(marker)[1].strip() + '\nAnything else?'
                break
        return response, answer

    @staticmethod
    def get_devices() -> dict:
        """
        Gets the devices from the altered_bytes package by running a script
        {
            '192.168.0.10': {'state': 'OFF', 'title': 'gold_lamp_living'}, 
            '192.168.0.120': {'state': 'ON', 'title': 'print_3d_office'}, 
            '192.168.0.216': {'state': 'OFF', 'title': 'side_lamp_living'}, 
            '192.168.0.251': {'state': 'OFF', 'title': 'light_strip_terrasse'}, 
            '192.168.0.55': {'state': 'OFF', 'title': 'panel_led_lamp_office'}
            }
        Then converts it to a nice tabulate table
            |+---------------+-------+-----------------------+
            |      IP       | state |         title         |
            +---------------+-------+-----------------------+
            | 192.168.0.10  |  OFF  |   gold_lamp_living    |
            | 192.168.0.120 |  ON   |    print_3d_office    |
            | 192.168.0.216 |  OFF  |   side_lamp_living    |
            | 192.168.0.251 |  OFF  | light_strip_terrasse  |
            | 192.168.0.55  |  OFF  | panel_led_lamp_office |
            +---------------+-------+-----------------------+
        """
        script_path = r"C:/Users/lars/python_venvs/packages/altered_bytes/altered/devices.py"
        try:
            # Single line for subprocess call and processing
            raw_output = subprocess.run([sys.executable, script_path],
                                            capture_output=True,
                                            text=True,
                                            check=True
                        ).stdout.strip()
            # Parse the output to get the devices json string
            json_str = re.search(r"(?<=\n)\{.*\}", raw_output, re.DOTALL)
            try:
                devices = ast.literal_eval(json_str.group(0))
                # Convert to a tabulate table
                if not devices:
                    return f"ERROR creating devices table: {raw_output = }"
                return tb([{'IP': ip, **vs} for ip, vs in devices.items()], 
                            headers="keys", tablefmt="pretty")
            except (SyntaxError, ValueError) as e:
                print(f"{Fore.RED}ERROR: chat_llm.Assistant.get_devices:{Fore.RESET} "
                        f"Failed to parse devices output: {e}")
                return f"ERROR parsing status info: {raw_output = }"
        except Exception as e:
            print(f"{Fore.RED}ERROR: chat_llm.Assistant.get_devices:{Fore.RESET} "
                    f"Failed to get devices: \n{e = }")
            return f"ERROR getting devices: {raw_output = }"


class Chat:
    
    def __init__(self) -> None:
        """
        Initialize the Chat with an App instance, an Assistant instance, and
        store the initial user message count.
        """
        self.app = App()
        self.assistant = Assistant()
        self.prev_user_count = self.app.conv_manager.msg_count_user

    def monitor_conversation(self) -> None:
        """
        Monitor the conversation continuously. Each time a new user message
        is detected (i.e. the user message count increases), call the 
        assistant_response method and add its result as an assistant message 
        to the conversation.
        """
        try:
            while True:
                curr_user_count = self.app.conv_manager.msg_count_user
                if curr_user_count != self.prev_user_count:
                    last_user_msg = self.app.conversation.get_last_message(role="user")
                    if '/bye' in last_user_msg:
                        self.running = False
                        raise KeyboardInterrupt
                    response, answer = self.assistant.get_response(last_user_msg)
                    self.app.conversation.append_message(
                                                    role="assistant", 
                                                    content=answer if answer else response
                    )
                    self.prev_user_count = curr_user_count
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down conversation monitoring...")

    def run(self) -> None:
        """
        Start the conversation monitor in a background thread and then run the 
        App in the main thread.
        """
        monitor_thread = threading.Thread(target=self.monitor_conversation)
        monitor_thread.daemon = True
        monitor_thread.start()
        self.app.run()

# if __name__ == "__main__":
#     print(Assistant.get_devices())

if __name__ == "__main__":
    chat = Chat()
    chat.run()
