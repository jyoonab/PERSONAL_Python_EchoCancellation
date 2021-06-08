# Libraries
import sounddevice as sd  # sound device management
import tkinter as tk  # GUI
from tkinter import ttk  # GUI
from tkinter import messagebox  # GUI
import win32api  # windows api
import psutil  # process management
import tempfile  # temp file management in cross-platform
import os  # os management
import shutil  # os file management


# Constant Declaration
TARGET_VIRTUAL_DEVICE = 'CABLE Input'
INPUT_EXCEPT_DEVICE_LIST = ['CABLE Output', 'Microsoft Sound Mapper - Input', 'Microsoft Sound Mapper - Output',
                      '주 사운드 캡처 드라이버', '주 사운드 드라이버', '라인 입력', 'Output ()', '스테레오 믹스']
OUTPUT_EXCEPT_DEVICE_LIST = ['CABLE Output', 'Microsoft Sound Mapper - Input', 'Microsoft Sound Mapper - Output',
                      '주 사운드 캡처 드라이버', '주 사운드 드라이버', '라인 입력', 'Output ()', '마이크']

# Global variable declaration
isRunning = False  # Flag of start button clicked event


class App(tk.Tk):
    def __init__(self):
        super().__init__()  # Inheritance from tkinter class
        # Construct GUI(Graphical User Interface) object
        self.title("Real Time AEC")
        self.geometry("600x100")
        self.resizable(0, 0)

        quality_level_list = ['High(강력한 소음 및 에코 억제)', 'Medium(적당한 소음 및 에코 억제)', 'Low(약간의 소음 및 에코 억제)']
        input_device_dict, output_device_dict = Function.get_audio_devices()

        input_device_label = tk.Label(self, text="Input Devices :")
        input_device_label.grid(column=0, row=0)

        input_device_combo = ttk.Combobox(self, state="readonly", width=50,
                                          values=list(input_device_dict.keys()))
        input_device_combo.grid(column=1, row=0)
        input_device_combo.current(0)
        input_device_combo.bind("<<ComboboxSelected>>", lambda _:
        Function.fit_audio_device_channel(input_device_combo.get(), output_device_combo, output_device_dict))

        output_device_label = tk.Label(self, text="Output Devices :")
        output_device_label.grid(column=0, row=1)

        output_device_combo = ttk.Combobox(self, state="readonly", width=50,
                                           values=list(output_device_dict.keys()))
        output_device_combo.grid(column=1, row=1)
        output_device_combo.current(0)

        # fit default input channel and output channel
        Function.fit_audio_device_channel(input_device_combo.get(), output_device_combo, output_device_dict)

        quality_level_label = tk.Label(self, text="Quality Enhancement Level :")
        quality_level_label.grid(column=0, row=2)

        quality_level_combo = ttk.Combobox(self, state="readonly", width=50, values=quality_level_list)
        quality_level_combo.grid(column=1, row=2)
        quality_level_combo.current(0)

        start_button = tk.Button(self, overrelief="solid", width=15, text="Start", repeatdelay=1000, repeatinterval=100,
                                 command=lambda: Function.start_button_clicked(start_button,
                                                                               input_device_combo,
                                                                               output_device_combo,
                                                                               quality_level_combo,
                                                                               input_device_dict,
                                                                               output_device_dict))
        start_button.grid(column=0, row=3)


class Function:
    @staticmethod
    def start_button_clicked(start_button, input_device_combo, output_device_combo, quality_level_combo,
                             input_device_dict, output_device_dict):
        """ This function is the click event trigger of the start button. """
        # Getting the selected value from combobox
        global isRunning
        if not isRunning:
            isRunning = True  # Flag change
            # get devices index
            input_device_index = input_device_dict[input_device_combo.get()]
            output_device_index = output_device_dict[output_device_combo.get()]
            quality_level_index = quality_level_combo.current()

            # kill process
            for process in psutil.process_iter():
                try:
                    process_name = process.name()
                    if process_name == "windows_aec.exe":
                        process.kill()
                except Exception as ex:
                    messagebox.showinfo("Sorry :<", f'Error Occurred: {str(ex)}')
                    continue

            # make a args and execute aec
            args = 'windows_aec.exe --input {0} --output {1} --level {2}'\
                .format(input_device_index, output_device_index, quality_level_index, int(240))
            try:
                win32api.WinExec(args)
            except Exception as ex:
                messagebox.showinfo("Sorry :<", f'Error Occurred: {str(ex)}')

            # change GUI
            start_button['text'] = 'Stop'
            start_button.configure(fg='red')

        else:
            isRunning = False  # Flag change
            # kill process
            for process in psutil.process_iter():
                try:
                    process_name = process.name()
                    if process_name == "windows_aec.exe":
                        process.kill()
                except Exception as ex:
                    messagebox.showinfo("Sorry :<", f'Error Occurred: {str(ex)}')
                    continue

            # delete temp directory
            temp_directory = tempfile.gettempdir()
            file_list = os.listdir(temp_directory)
            for file_name in file_list:
                file_path = os.path.join(temp_directory, file_name)
                if '_MEI' in file_name and os.path.isdir(file_path):  # find python temporary files
                    # noinspection PyBroadException
                    try:
                        shutil.rmtree(file_path)
                    except:
                        continue

            # change GUI
            start_button['text'] = 'Start'
            start_button.configure(fg='black')


    @staticmethod
    def get_audio_devices():
        """ This function get input/output audio device information """
        device_list: object = sd.query_devices()
        hostapi_list = []
        input_device_dict, output_device_dict = {}, {}
        breaker = False  # loop break flag

        # [1] make output_device_dict
        for index, device in enumerate(device_list):
            # Except useless device
            if device['default_samplerate'] != 44100.0:  # if not sample rate 44100:
                continue

            # double loop for apply except devices
            for except_device in OUTPUT_EXCEPT_DEVICE_LIST:
                if except_device in device['name']:
                    breaker = True
                    break
            if breaker:  # breaker == True
                breaker = False
                continue

            if '(' in device['name']:
                device['name'] = device['name'][0:device['name'].index('(')]

            if TARGET_VIRTUAL_DEVICE in device['name']:
                device['name'] = '딥러닝 기반 음향 품질향상 모드'
            device_name = '{0}(channel:{1})'.format(device['name'], str(device['hostapi']))
            device_name = device_name.replace(' (', '(')
            output_device_dict[device_name] = index
            hostapi_list.append(device['hostapi'])

        # [2] make input_device_dict
        for index, device in enumerate(device_list):
            # Except useless device
            if device['default_samplerate'] != 44100.0:  # if not sample rate 44100:
                continue

            # double loop for apply except devices
            for except_device in INPUT_EXCEPT_DEVICE_LIST:
                if except_device in device['name']:
                    breaker = True
                    break
            if breaker:  # breaker == True
                breaker = False
                continue

            if device['max_input_channels'] != 0 and device["max_output_channels"] == 0:
                if device['hostapi'] in hostapi_list:
                    if '(' in device['name']:
                        device_name = device['name'][:device['name'].index('(')]
                        device_name = '{0}(channel:{1})'.format(device_name, str(device['hostapi']))
                    else:
                        device_name = '{0}(channel:{1})'.format(device['name'], str(device['hostapi']))
                    device_name = device_name.replace(' (', '(')
                    input_device_dict[device_name] = index

        return input_device_dict, output_device_dict

    @staticmethod
    def fit_audio_device_channel(device_name, output_device_combo, output_device_dict):
        target_channel_code = device_name[-11:]
        fit_audio_device_dict = output_device_dict.copy()

        # search target output devices
        for output_device in output_device_dict:
            if target_channel_code not in output_device:
                del fit_audio_device_dict[output_device]

        # apply change
        output_device_combo['values'] = list(fit_audio_device_dict.keys())
        output_device_combo.current(0)


if __name__ == '__main__':
    app = App()
    app.mainloop()  # execute GUI
