#!/usr/bin/env python3

# Libraries
import sounddevice as sd
import numpy as np
import tensorflow.lite as tf_lite
import argparse
import time
import matplotlib.pyplot as plt
import asyncio

a = [0] * 4

class WindowsAEC:
    def __init__(self, quality_enhancement_level):

        self.block_shift = 128  # audio block shift
        self.block_len = 512  # audio block length
        self.sampling_rate = 16000  # sampling rate
        self.sound_device_latency = 0.2  # latency of callback
        self.reboot = False  # reboot signal flag

        # Set model name
        self.model_name_1 = 'high_model_1.tflite'
        self.model_name_2 = 'high_model_2.tflite'
        if quality_enhancement_level == 0:
            print("quant")
            self.model_name_1 = './quant_model/model_quantization_1.tflite'
            self.model_name_2 = './quant_model/model_quantization_2.tflite'
        elif quality_enhancement_level == 1:
            self.model_name_1 = 'medium_model_1.tflite'
            self.model_name_2 = 'medium_model_2.tflite'
        elif quality_enhancement_level == 2:
            print("low")
            self.model_name_1 = 'low_model_1.tflite'
            self.model_name_2 = 'low_model_2.tflite'

        self.interpreter_1 = tf_lite.Interpreter(model_path=self.model_name_1, num_threads=None)
        self.interpreter_1.allocate_tensors()

        self.interpreter_2 = tf_lite.Interpreter(model_path=self.model_name_2, num_threads=None)
        self.interpreter_2.allocate_tensors()

        # Get input and output tensors.
        self.input_details_1 = self.interpreter_1.get_input_details()
        self.output_details_1 = self.interpreter_1.get_output_details()

        self.input_details_2 = self.interpreter_2.get_input_details()
        self.output_details_2 = self.interpreter_2.get_output_details()

        # create states for the Dual-signal Transformation LSTM
        self.states_1 = np.zeros(self.input_details_1[1]['shape']).astype('float32')
        self.states_2 = np.zeros(self.input_details_2[1]['shape']).astype('float32')

        # create buffer
        self.in_buffer = np.zeros(self.block_len).astype('float32')
        self.out_buffer = np.zeros(self.block_len).astype('float32')

    def Start(self, input_device_index, output_device_index):
        with sd.Stream(device=(input_device_index, output_device_index),
                       samplerate=self.sampling_rate, blocksize=self.block_shift,
                       dtype=np.float32, latency=self.sound_device_latency,
                       channels=1, callback=self.callback) as stream_object:
            #input()
            while stream_object.active:
                time.sleep(0)

    def callback(self, indata, outdata, frames, time, status):
        global a
        """ This function handle audio stream data """


        if status:
            print(status)
            outdata[:] = indata
            raise sd.CallbackStop()

        # write to buffer
        self.in_buffer[:-self.block_shift] = self.in_buffer[self.block_shift:]
        self.in_buffer[-self.block_shift:] = np.squeeze(indata)

        # fft & create magnitude & reshape magnitude to input dimensions
        in_block_fft = np.fft.rfft(np.squeeze(self.in_buffer)).astype("complex64")
        in_mag = np.abs(in_block_fft)
        in_mag = np.reshape(in_mag, (1, 1, -1)).astype("float32")

        # set tensors to the first model
        self.interpreter_1.set_tensor(self.input_details_1[0]["index"], in_mag)
        self.interpreter_1.set_tensor(self.input_details_1[1]["index"], self.states_1)

        # run calculation
        self.interpreter_1.invoke()

        # get the output of the first block
        out_mask = self.interpreter_1.get_tensor(self.output_details_1[0]["index"])
        self.states_1 = self.interpreter_1.get_tensor(self.output_details_1[1]["index"])

        # apply mask and calculate the IFFT
        estimated_block = np.fft.irfft(in_block_fft * out_mask)
        estimated_block = np.reshape(estimated_block, (1, 1, -1)).astype("float32")

        # set tensors to the second block
        self.interpreter_2.set_tensor(self.input_details_2[0]["index"], estimated_block)
        self.interpreter_2.set_tensor(self.input_details_2[1]["index"], self.states_2)

        self.interpreter_2.invoke()

        # get output tensors
        out_block = self.interpreter_2.get_tensor(self.output_details_2[0]['index'])
        self.states_2 = self.interpreter_2.get_tensor(self.output_details_2[1]['index'])

        #print('out_block ', out_mask)
        #print('self.states_2 ', self.states_2)

        # exception handle
        if 'nan' in str(out_block[0, 0][0]):
            self.reboot = True
            print('nan error occurred!')
            raise sd.CallbackAbort()

        # write to buffer
        self.out_buffer[:-self.block_shift] = self.out_buffer[self.block_shift:]
        self.out_buffer[-self.block_shift:] = np.zeros(self.block_shift)
        self.out_buffer += np.squeeze(out_block)

        #volume_before = int(np.linalg.norm(indata)*10)
        #volume_after = int(np.linalg.norm(np.expand_dims(self.out_buffer[:self.block_shift], axis=-1))*10)
        #print("|" * int(volume_before))
        #print("#" * int(volume_after))

        a[:-1] = a[1:]
        a[-1:] = [int(np.linalg.norm(indata)*10)]

        volume_before = a[0]
        volume_after = int(np.linalg.norm(np.expand_dims(self.out_buffer[:self.block_shift], axis=-1))*10)
        #print("|" * int(volume_before))
        #print("#" * int(volume_after))

        #if int(volume_before) != 0:
        #    print("|" * int(volume_before))
        #    print("#" * int(volume_after))

        # clean voice(type: time-domain) -> outdata(type: time-domain) -> output_device
        outdata[:] = np.expand_dims(self.out_buffer[:self.block_shift], axis=-1)



# Exception handle

while True:
    windows_aec = WindowsAEC(2)
    while True:
        if not windows_aec.reboot:
            windows_aec.Start(1, 4)
        else:
            break  # break the while
