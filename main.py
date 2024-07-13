# 导入所需的库
import json
import requests
import time
import threading
import tkinter as tk
from tkinter import scrolledtext
from queue import Queue, Empty
import textwrap
import sys

def send_request(messages, response_queue, stop_event):
    """发送请求到AI服务器并处理响应"""
    # API端点
    url = "http://aidodoapi.ates.top:3000/v1/chat/completions"
    # 请求头
    headers = {
        'Authorization': 'Bearer sk-7C6d3vJK6LTKvuN5Eb6091Ff7663440cB703B17628907291',
        'Content-Type': 'application/json; charset=utf-8'
    }
    # 请求体
    payload = {
        "messages": messages,
        "model": "claude-3-5-sonnet-20240620",
        "stream": True,
    }

    start_time = time.time()
    first_response_time = None
    try:
        # 发送POST请求
        with requests.post(url, headers=headers, json=payload, stream=True) as response:
            response.raise_for_status()
            full_response = ""
            # 逐行处理响应
            for line in response.iter_lines():
                if stop_event.is_set():
                    break
                if line:
                    line = line.decode('utf-8').strip()
                    if line == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        try:
                            # 解析JSON响应
                            content = json.loads(line[6:])['choices'][0]['delta'].get('content', '')
                            if content:
                                if first_response_time is None:
                                    first_response_time = time.time()
                                full_response += content
                                response_queue.put(('content', content))
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
            # 计算响应时间
            total_time = round(time.time() - start_time, 2)
            time_to_first_response = round(first_response_time - start_time, 2) if first_response_time else None
            response_queue.put(('time', (total_time, time_to_first_response)))
            return full_response, total_time, time_to_first_response
    except requests.RequestException as e:
        # 处理请求异常
        response_queue.put(('error', str(e)))
        return None, round(time.time() - start_time, 2), None

class ChatApp:
    """图形界面聊天应用类"""
    def __init__(self, master):
        self.master = master
        self.master.title("AI 聊天应用")

        # 获取屏幕尺寸
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()

        # 设置窗口大小
        window_width = int(screen_width * 0.8)
        window_height = int(screen_height * 0.8)

        # 设置窗口位置
        self.master.geometry(f"{window_width}x{window_height}+{int(screen_width*0.1)}+{int(screen_height*0.1)}")

        # 设置基础字体大小
        self.base_font_size = int(screen_height / 50)

        # 初始化消息列表和队列
        self.messages = []
        self.response_queue = Queue()
        self.stop_event = threading.Event()

        # 创建GUI组件
        self.create_widgets()

    def create_widgets(self):
        """创建GUI组件"""
        # 创建聊天框架
        self.chat_frame = tk.Frame(self.master)
        self.chat_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # 创建聊天日志文本框
        self.chat_log = scrolledtext.ScrolledText(self.chat_frame, wrap=tk.WORD, font=('TkDefaultFont', self.base_font_size))
        self.chat_log.pack(expand=True, fill=tk.BOTH)
        self.chat_log.config(state=tk.DISABLED)

        # 创建输入框架
        self.input_frame = tk.Frame(self.master)
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)

        # 创建消息输入文本框
        self.message_entry = tk.Text(self.input_frame, height=3, font=('TkDefaultFont', self.base_font_size), wrap=tk.WORD)
        self.message_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.message_entry.bind("<Shift-Return>", self.send_message)
        self.message_entry.bind("<Return>", self.handle_return)

        # 创建发送按钮
        self.send_button = tk.Button(self.input_frame, text="发送", command=self.send_message, font=('TkDefaultFont', self.base_font_size))
        self.send_button.pack(side=tk.RIGHT)

        # 创建停止按钮
        self.stop_button = tk.Button(self.input_frame, text="停止", command=self.stop_response, font=('TkDefaultFont', self.base_font_size))
        self.stop_button.pack(side=tk.RIGHT, padx=(0, 10))

    def handle_return(self, event):
        """处理回车键事件"""
        self.message_entry.insert(tk.INSERT, "\n")
        return "break"

    def send_message(self, event=None):
        """发送消息"""
        message = self.message_entry.get("1.0", tk.END).strip()
        if message:
            # 清空输入框
            self.message_entry.delete("1.0", tk.END)
            # 在聊天日志中显示用户消息
            self.chat_log.config(state=tk.NORMAL)
            self.chat_log.insert(tk.END, f"用户: {message}\n\n")
            self.chat_log.config(state=tk.DISABLED)
            self.chat_log.see(tk.END)

            # 将消息添加到消息列表
            self.messages.append({"role": "user", "content": message})
            
            # 在聊天日志中显示AI助手的回复前缀
            self.chat_log.config(state=tk.NORMAL)
            self.chat_log.insert(tk.END, "AI助手: ")
            self.chat_log.config(state=tk.DISABLED)
            
            # 清除停止事件标志
            self.stop_event.clear()
            # 在新线程中获取AI响应
            threading.Thread(target=self.get_ai_response).start()
            # 开始处理响应
            self.master.after(100, self.process_response)

    def get_ai_response(self):
        """获取AI响应"""
        send_request(self.messages, self.response_queue, self.stop_event)

    def process_response(self):
        """处理AI响应"""
        try:
            response_type, data = self.response_queue.get_nowait()
            if response_type == 'content':
                # 显示内容
                self.chat_log.config(state=tk.NORMAL)
                self.chat_log.insert(tk.END, data)
                self.chat_log.config(state=tk.DISABLED)
                self.chat_log.see(tk.END)
            elif response_type == 'time':
                # 显示响应时间
                total_time, time_to_first_response = data
                self.chat_log.config(state=tk.NORMAL)
                self.chat_log.insert(tk.END, f"\n\n首次响应时间: {time_to_first_response:.2f} 秒\n")
                self.chat_log.insert(tk.END, f"总耗时: {total_time:.2f} 秒\n\n")
                self.chat_log.config(state=tk.DISABLED)
                self.chat_log.see(tk.END)
                return
            elif response_type == 'error':
                # 显示错误信息
                self.chat_log.config(state=tk.NORMAL)
                self.chat_log.insert(tk.END, f"\n错误: {data}\n\n")
                self.chat_log.config(state=tk.DISABLED)
                self.chat_log.see(tk.END)
                return
            self.master.after(10, self.process_response)
        except Empty:
            self.master.after(100, self.process_response)

    def stop_response(self):
        """停止AI响应"""
        self.stop_event.set()
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, "\n[响应已停止]\n\n")
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.see(tk.END)

class TerminalChat:
    """终端聊天应用类"""
    def __init__(self):
        self.messages = []
        self.response_queue = Queue()
        self.stop_event = threading.Event()
        self.stop_window = None

    def create_stop_window(self):
        """创建停止窗口"""
        self.stop_window = tk.Tk()
        self.stop_window.title("停止 AI 输出")
        self.stop_window.geometry("200x100")
        stop_button = tk.Button(self.stop_window, text="停止 AI 输出", command=self.stop_response)
        stop_button.pack(expand=True)

    def chat(self):
        """开始聊天"""
        self.create_stop_window()
        threading.Thread(target=self.terminal_input).start()
        self.stop_window.mainloop()

    def terminal_input(self):
        """处理终端输入"""
        print("欢迎使用多行输入模式。输入您的消息，按两次Enter键发送。输入'退出'、'exit'或'quit'结束对话。")
        while True:
            print("\n用户: ", end='')
            lines = []
            while True:
                line = input()
                if line.strip() == "":
                    break
                lines.append(line)
            user_input = "\n".join(lines).strip()

            if user_input.lower() in ['退出', 'exit', 'quit']:
                self.stop_window.quit()
                break

            if user_input:
                self.messages.append({"role": "user", "content": user_input})
                print("\nAI助手: ", end='', flush=True)
                
                self.stop_event.clear()
                threading.Thread(target=self.get_ai_response).start()
                
                self.process_response()

    def get_ai_response(self):
        """获取AI响应"""
        send_request(self.messages, self.response_queue, self.stop_event)

    def process_response(self):
        """处理AI响应"""
        full_response = ""
        start_time = time.time()
        first_response_time = None
        while True:
            try:
                response_type, data = self.response_queue.get(timeout=0.1)
                if response_type == 'content':
                    if first_response_time is None:
                        first_response_time = time.time()
                    full_response += data
                    print(data, end='', flush=True)
                elif response_type == 'time':
                    total_time, _ = data
                    print(f"\n首次响应时间: {first_response_time - start_time:.2f} 秒")
                    print(f"总耗时: {total_time} 秒")
                    self.messages.append({"role": "assistant", "content": full_response})
                    break
                elif response_type == 'error':
                    print(f"\n错误: {data}")
                    break
            except Empty:
                if self.stop_event.is_set():
                    print("\n[响应已停止]")
                    break
        print("\n" + "="*50)

    def stop_response(self):
        """停止AI响应"""
        self.stop_event.set()

def choose_mode():
    """选择运行模式"""
    root = tk.Tk()
    root.title("选择模式")
    root.geometry("300x150")

    def start_terminal():
        """启动终端模式"""
        root.destroy()
        TerminalChat().chat()

    def start_gui():
        """启动图形界面模式"""
        root.destroy()
        main_root = tk.Tk()
        ChatApp(main_root)
        main_root.mainloop()

    tk.Label(root, text="请选择使用模式", font=('TkDefaultFont', 14)).pack(pady=10)
    tk.Button(root, text="终端模式", command=start_terminal).pack(pady=5)
    tk.Button(root, text="图形界面模式", command=start_gui).pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    choose_mode()

