#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to check if a command is available
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Heroku CLI is installed
if ! command_exists heroku; then
    echo "Error: Heroku CLI is not installed. Please install it first."
    exit 1
fi

# Function to compare version numbers correctly
version_greater_equal() {
    [ "$1" = "$2" ] && return 0
    local IFS=.
    local i version1=($1) version2=($2)
    for ((i=${#version1[@]}; i<${#version2[@]}; i++)); do
        version1[i]=0
    done
    for ((i=0; i<${#version1[@]}; i++)); do
        if [[ -z ${version2[i]} ]]; then
            version2[i]=0
        fi
        if ((10#${version1[i]} > 10#${version2[i]})); then
            return 0
        fi
        if ((10#${version1[i]} < 10#${version2[i]})); then
            return 1
        fi
    done
    return 0
}

# Check Heroku CLI version and provide instructions if version is outdated
current_version=$(heroku --version | grep -oP 'heroku/\K\d+\.\d+\.\d+')
required_version="9.2.1"

if ! version_greater_equal "$current_version" "$required_version"; then
    echo "Your Heroku CLI version ($current_version) is outdated. The required version is $required_version."
    if ! command_exists npm; then
        echo "npm is not installed. Please follow these steps to install npm and update Heroku CLI:"
        echo ""
        echo "1. Install npm:"
        echo "   - For Ubuntu/Debian: sudo apt-get update && sudo apt-get install npm"
        echo "   - For macOS (using Homebrew): brew install node"
        echo "   - For Windows: Download and install Node.js from https://nodejs.org/"
        echo ""
        echo "2. After installing npm, update Heroku CLI by running:"
        echo "   npm install -g heroku@$required_version"
        echo ""
        echo "Please install npm, update Heroku CLI, and then run this script again."
        exit 1
    else
        echo "Updating Heroku CLI to version $required_version..."
        if ! npm install -g heroku@$required_version; then
            echo "Error: Failed to update Heroku CLI. Please update it manually to version $required_version."
            exit 1
        fi
        echo "Heroku CLI updated successfully."
    fi
else
    echo "Heroku CLI is up to date (version $current_version)."
fi

# Check if git is installed
if ! command_exists git; then
    echo "Error: Git is not installed. Please install it first."
    exit 1
fi

# Ensure the user is logged in to Heroku
if ! heroku auth:whoami &>/dev/null; then
    echo "You need to log in to Heroku CLI. Running 'heroku login'..."
    heroku login
    if [ $? -ne 0 ]; then
        echo "Error: Failed to log in to Heroku. Please log in manually and run the script again."
        exit 1
    fi
else
    echo "You are already logged in to Heroku."
fi

# Function to create or select a Heroku app
create_or_select_app() {
    local app_name=""
    local max_attempts=3
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        read -p "Enter your Heroku app name (leave blank to create a new one): " input_app_name

        if [ -z "$input_app_name" ]; then
            echo "Creating a new Heroku app..."
            app_info=$(heroku create)
            if [ $? -eq 0 ]; then
                app_name=$(echo "$app_info" | grep -oP '(?<=Creating ).*(?=\.\.\. done)')
                echo "Created new app: $app_name"
                echo "Waiting for Heroku to process the app creation..."
                sleep 5
                break
            else
                echo "Error: Failed to create a new Heroku app."
                ((attempt++))
                continue
            fi
        else
            app_name="$input_app_name"
            echo "Checking if app '$app_name' exists..."
            if heroku apps:info -a "$app_name" &> /dev/null; then
                echo "App '$app_name' found. Setting it as the remote."
                heroku git:remote -a "$app_name"
                break
            else
                echo "App '$app_name' not found. Would you like to create it? (y/n)"
                read create_app
                if [[ $create_app =~ ^[Yy]$ ]]; then
                    if heroku create "$app_name"; then
                        echo "Created new app: $app_name"
                        echo "Waiting for Heroku to process the app creation..."
                        sleep 5
                        break
                    else
                        echo "Error: Failed to create app '$app_name'."
                        ((attempt++))
                        continue
                    fi
                else
                    echo "App creation skipped. Please enter a valid existing app name."
                    ((attempt++))
                    continue
                fi
            fi
        fi
    done

    if [ $attempt -gt $max_attempts ]; then
        echo "Error: Max attempts reached. Unable to create or select app."
        echo "Please ensure you have the necessary permissions to create or access Heroku apps."
        echo "You can try the following:"
        echo "1. Check your Heroku account status and permissions."
        echo "2. Verify that you're logged in to the correct Heroku account."
        echo "3. Try creating the app manually using 'heroku create <app-name>' and then run this script again."
        return 1
    fi

    echo "Verifying app '$app_name' exists..."
    if ! heroku apps:info -a "$app_name" &> /dev/null; then
        echo "Error: App '$app_name' not found after creation. This could be due to:"
        echo "1. Network issues"
        echo "2. Heroku API temporary unavailability"
        echo "3. Insufficient permissions"
        echo "Please try the following:"
        echo "1. Wait a few minutes and run the script again."
        echo "2. Check your internet connection."
        echo "3. Verify your Heroku account permissions."
        echo "4. Try creating the app manually using 'heroku create $app_name' and then run this script again."
        return 1
    fi

    echo "App '$app_name' verified successfully."
    echo "$app_name"
}

# Create a new Heroku app or use an existing one
app_name=$(create_or_select_app)

if [ -z "$app_name" ]; then
    echo "Error: Failed to create or select Heroku app. Please try again."
    exit 1
fi

# Function to set Heroku stack with retry
set_heroku_stack() {
    local max_retries=3
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        echo "Setting Heroku stack to Heroku-24 (Attempt $((retry_count + 1))/$max_retries)..."
        if heroku stack:set heroku-24 -a "$app_name"; then
            echo "Heroku stack set successfully."
            return 0
        else
            echo "Failed to set Heroku stack. Retrying in 5 seconds..."
            sleep 5
            ((retry_count++))
        fi
    done

    echo "Error: Failed to set Heroku stack after $max_retries attempts."
    echo "This could be due to:"
    echo "1. Network issues"
    echo "2. Heroku API temporary unavailability"
    echo "3. Insufficient permissions"
    echo "Please try the following:"
    echo "1. Wait a few minutes and run the script again."
    echo "2. Check your internet connection."
    echo "3. Verify your Heroku account permissions."
    echo "4. Try setting the stack manually using 'heroku stack:set heroku-24 -a $app_name' and then continue with the deployment."
    return 1
}

# Verify app exists and set the Heroku stack
if heroku apps:info -a "$app_name" &> /dev/null; then
    if ! set_heroku_stack; then
        exit 1
    fi
else
    echo "Error: App '$app_name' not found. Unable to set Heroku stack."
    echo "This could be due to:"
    echo "1. The app was deleted after creation"
    echo "2. Network issues"
    echo "3. Heroku API temporary unavailability"
    echo "Please try the following:"
    echo "1. Wait a few minutes and run the script again."
    echo "2. Check your internet connection."
    echo "3. Verify that the app still exists in your Heroku dashboard."
    echo "4. If the app doesn't exist, try creating it manually using 'heroku create $app_name' and then run this script again."
    exit 1
fi

# Set the Python version for Heroku
echo "python-3.9.16" > runtime.txt

# Add and commit changes
echo "Adding and committing changes..."
git add .
git commit -m "Prepare for Heroku deployment" || {
    echo "No changes to commit. Continuing with deployment..."
}

# Push to Heroku
echo "Deploying to Heroku..."
if ! git push heroku main; then
    echo "Error: Failed to deploy to Heroku."
    echo "Checking if the 'main' branch exists..."
    if git show-ref --verify --quiet refs/heads/main; then
        echo "'main' branch exists. Trying to push again..."
        if ! git push heroku main; then
            echo "Error: Failed to deploy to Heroku again. This could be due to:"
            echo "1. Network issues"
            echo "2. Heroku API temporary unavailability"
            echo "3. Git configuration problems"
            echo "Please try the following:"
            echo "1. Wait a few minutes and run the script again."
            echo "2. Check your internet connection."
            echo "3. Verify your Git configuration and Heroku remote."
            echo "4. Try pushing manually using 'git push heroku main' and check for more detailed error messages."
            exit 1
        fi
    else
        echo "'main' branch does not exist. Trying to push 'master' branch..."
        if ! git push heroku master; then
            echo "Error: Failed to deploy to Heroku using 'master' branch. This could be due to:"
            echo "1. Network issues"
            echo "2. Heroku API temporary unavailability"
            echo "3. Git configuration problems"
            echo "4. Neither 'main' nor 'master' branch exists"
            echo "Please try the following:"
            echo "1. Wait a few minutes and run the script again."
            echo "2. Check your internet connection."
            echo "3. Verify your Git configuration and Heroku remote."
            echo "4. Ensure you have either a 'main' or 'master' branch in your repository."
            echo "5. Try pushing manually using 'git push heroku <your-branch-name>:main' and check for more detailed error messages."
            exit 1
        fi
    fi
fi

# Open the app in the browser
echo "Opening the app in your default browser..."
heroku open -a "$app_name"

# Deployment completed
echo "Deployment completed successfully!"
