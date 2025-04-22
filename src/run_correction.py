#!/usr/bin/env python
# coding: utf-8

import os
import argparse
import sys
import numpy as np
import tensorflow as tf
import subprocess
import time
from colorama import Fore, Style, init

# Initialize colorama for colored console output
init(autoreset=True)

def print_header():
    """Print header for the climate model bias correction tool."""
    header = f"""
{Fore.CYAN}============================================================
{Fore.CYAN}||       GLOBAL CLIMATE MODEL ERROR CORRECTION TOOLKIT     ||
{Fore.CYAN}============================================================{Style.RESET_ALL}
    """
    print(header)

def print_section(title):
    """Print a section title."""
    print(f"\n{Fore.YELLOW}=== {title} ==={Style.RESET_ALL}\n")

def print_success(message):
    """Print a success message."""
    print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")

def print_info(message):
    """Print an information message."""
    print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")

def print_error(message):
    """Print an error message."""
    print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")

def check_gpu_availability():
    """Check if GPU is available for TensorFlow."""
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print_success(f"Found {len(gpus)} GPU(s): {', '.join([gpu.name for gpu in gpus])}")
        # Get GPU details
        for gpu in gpus:
            try:
                gpu_details = tf.config.experimental.get_device_details(gpu)
                print_info(f"  - {gpu.name}: {gpu_details.get('device_name', 'Unknown')}")
            except:
                pass
        return True
    else:
        print_info("No GPUs found. Training will run on CPU.")
        return False

def check_data_availability(variable):
    """Check if data files for the specified variable exist."""
    
    # Define required base directories based on the variable
    if variable == "sss":
        base_dir = "../data/sss/"
        essential_files = [
            f"{base_dir}cmip6_sss_1958_2014_fill_diststen.mat",
            f"{base_dir}oras5_sss_1958_2014_fill_diststen.mat",
            f"{base_dir}oras5_historical_sss_1958_2020_mean.mat"
        ]
    elif variable == "s200mavg":
        base_dir = "../data/so/"  # S200mavg is stored as so_200m in data structure
        essential_files = [
            f"{base_dir}cmip6_so_200m_1958_2014_fill_diststen.mat",
            f"{base_dir}oras5_so_200m_1958_2014_fill_diststen.mat",
            f"{base_dir}oras5_historical_so_200m_1958_2020_mean.mat"
        ]
    else:
        print_error(f"Unknown variable: {variable}")
        return False
    
    # Create directories if they don't exist
    required_dirs = [base_dir, "../output/", "../output/models/"]
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print_info(f"Created directory: {directory}")
    
    # Check for missing files
    missing_files = [f for f in essential_files if not os.path.exists(f)]
    
    if missing_files:
        print_error("Missing required data files:")
        for f in missing_files:
            print(f"  - {f}")
        return False
    else:
        print_success(f"All required data files for {variable.upper()} are available")
        return True

def list_variables():
    """List available variables for bias correction."""
    print_section("Available Variables for Bias Correction")
    
    variables = {
        "sss": "Sea Surface Salinity (SSS)",
        "s200mavg": "Salinity at 200m depth (S200mavg)"
    }
    
    for idx, (var_code, var_name) in enumerate(variables.items(), 1):
        print(f"{idx}. {Fore.CYAN}{var_code}{Style.RESET_ALL}: {var_name}")
    
    return variables

def run_correction(variable, epochs=None, batch_size=None, use_existing_model=False):
    """Run the UNet correction method for the specified variable."""
    print_section(f"Running UNet correction for {variable.upper()}")
    
    # Determine the correct script to run based on the variable
    if variable == "sss":
        script_path = "./sss_unet_reorganised.py"
    elif variable == "s200mavg":
        script_path = "./so_200m_unet_reorganised.py"
    else:
        print_error(f"Unknown variable: {variable}")
        return False
    
    # Check if script file exists
    if not os.path.exists(script_path):
        print_error(f"Script file not found: {script_path}")
        return False
    
    # Modify epochs, batch_size, and use_existing_model in the script if provided
    if epochs is not None or batch_size is not None or use_existing_model:
        try:
            with open(script_path, 'r') as file:
                script_contents = file.read()
            
            # Replace epochs value if provided
            if epochs is not None:
                script_contents = script_contents.replace("epochs=500", f"epochs={epochs}")
                script_contents = script_contents.replace("epochs=1000", f"epochs={epochs}")
                script_contents = script_contents.replace("epochs=2000", f"epochs={epochs}")
            
            # Replace batch_size value if provided
            if batch_size is not None:
                script_contents = script_contents.replace("batch_size=32", f"batch_size={batch_size}")
                script_contents = script_contents.replace("batch_size=64", f"batch_size={batch_size}")
            
            # Modify to use existing model if required
            if use_existing_model:
                # For UNet, add model loading before the create_model call
                model_creation_line = "model = create_unet_model()"
                var_folder = "sss" if variable == "sss" else "so_200m"
                model_loading_code = f"""try:
    print('Attempting to load existing UNet model...')
    model = keras.models.load_model('../output/models/unet_{var_folder}_model.h5', custom_objects={{"mse_loss": custom_mse_loss(mask)}})
    print('Loaded existing model')
except Exception as e:
    print('Creating new UNet model:', e)
    model = create_unet_model()"""
                script_contents = script_contents.replace(model_creation_line, model_loading_code)
            
            # Write modified content to a temporary file
            temp_script_path = f"./temp_{variable}_unet.py"
            with open(temp_script_path, 'w') as file:
                file.write(script_contents)
            
            script_path = temp_script_path
            
        except Exception as e:
            print_error(f"Error modifying script parameters: {str(e)}")
            return False
    
    # Run the script
    try:
        start_time = time.time()
        print_info(f"Starting execution of {script_path}")
        process = subprocess.Popen([sys.executable, script_path], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   universal_newlines=True)
        
        # Print output in real-time
        for stdout_line in iter(process.stdout.readline, ""):
            print(stdout_line.strip())
        process.stdout.close()
        
        # Handle errors
        for stderr_line in iter(process.stderr.readline, ""):
            print_error(stderr_line.strip())
        process.stderr.close()
        
        return_code = process.wait()
        end_time = time.time()
        
        # Clean up temporary file if created
        if epochs is not None or batch_size is not None or use_existing_model:
            try:
                os.remove(temp_script_path)
            except:
                pass
        
        if return_code == 0:
            elapsed_time = end_time - start_time
            print_success(f"{variable.upper()} correction completed successfully in {elapsed_time:.2f} seconds")
            return True
        else:
            print_error(f"{variable.upper()} correction failed with return code {return_code}")