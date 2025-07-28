# Free Models Guide

This guide provides a detailed walkthrough for setting up and using free AI models with TALKER. The best way to use free models is with the [LLM-API-Key-Proxy](https://github.com/Mirrowel/LLM-API-Key-Proxy), which helps you avoid rate limits and manage multiple API keys.

---

## Important Updates (July 2025)

*   **Chutes is No Longer Free**: Chutes has moved to a paid model(one-time, like openrouter). While this is a significant change, new free alternatives are being actively investigated and will be added to this guide as they become available.
*   **Community Impact**: The transition of Chutes to a paid service has unfortunately led to some users, particularly those generating NSFW content, migrating and abusing other free platforms. This has put a strain on those services, and their stability may be affected. Please use all services responsibly. Yes, blame Gooners. They killed Chutes for everyone and now they are killing the rest of the free services too(one already confirmed heavily impacted, with over 10x in usage).

---

### A Note on Thinking Models

"Thinking" models are designed for complex reasoning, which means they are often **considerably slower** than their non-thinking counterparts. For general use in the mod, **non-thinking models are usually the better choice** for a more responsive experience. However, **Gemini models are a notable exception**; their exceptional speed (Even Gemini Pro, which is faster and smarter than any other model on this list) makes them a powerful and viable option for thinking mode (In Auto MCM setting).

## Supported Free Providers
1.  **Gemini (Recommended)**: Gemini is known for its exceptional speed and solid intelligence, often outperforming other free services by a significant margin. This makes it an excellent choice for the "thinking mode" feature in TALKER, providing quick and coherent responses.
2.  **Chutes**: Chutes provides access to a diverse range of powerful models, including DeepSeek, Qwen, and Llama4. While this variety is a major advantage, be aware that popular, high-demand models can sometimes be unreliable or temporarily unavailable. Even with key rotation, a model that is down will not be accessible, so it's wise to have backup models or providers in mind.
3.  **Nvidia**: Nvidia offers a robust selection of high-quality models. Their `nvidia/llama-3.1-nemotron-ultra-253b-v1` is a particularly strong performer for both reasoning and general dialogue. They also host free versions of popular models like DeepSeek and Qwen, though the specific rate limits for these are not always clear.

---

## 1. Gemini (Recommended)

Google's Gemini is the top choice for its generous free tier and strong performance. By creating multiple projects, you can generate several API keys (up to 12 per account in our experience), which dramatically increases your free usage limits when used with the API proxy. Do note that it is recommended to use multiple accounts instead of maxing out projects - I don't have concrete evidence, but multiple users had their projects "banned" for some reason, and they were unable to create new projects or API keys. So multiple accounts with 2-4 keys each is more than enough.

### Models and Rate Limits

Gemini and Gemma models offer a range of options, each with different trade-offs between speed, intelligence, and rate limits.

**Gemini Models**

| Model Name (Provider Prefix)                     | Speed      | Intelligence | Notes                                                                                                                                                               |
| ------------------------------------------------ | ---------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemini/gemini-2.5-pro`                          | Slowest    | Smartest     | The most powerful model, ideal for complex dialogue and reasoning. Even as the "slowest" Gemini model, it's still faster than most non-Gemini models.                  |
| `gemini/gemini-2.5-flash`                        | Fast       | Smart        | **Recommended for most tasks.** A great balance of speed and intelligence, making it a versatile choice for both general use and thinking mode.                       |
| `gemini/gemini-2.5-flash-lite-preview-06-17`     | Fastest    | Decent       | The quickest model, perfect for fast-paced interactions where raw speed is the top priority.                                                                        |

**Gemma Models**

| Model Name (Provider Prefix)       | Speed      | Intelligence | Notes                                                                                                                                                               |
| ---------------------------------- | ---------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gemini/gemma-3-27b-it`            | Fast       | Good         | A strong performer that cannot reason. With enough keys, its high rate limit allows for virtually unlimited use, making it a great fallback option for non-reasoning tasks. |

**Free Tier Rate Limits (Per key)**

| Model                                    | RPM | TPM     | RPD    |
| ---------------------------------------- | --- | ------- | ------ |
| Gemini 2.5 Pro                           | 5   | 250,000 | 100    |
| Gemini 2.5 Flash                         | 10  | 250,000 | 250    |
| Gemini 2.5 Flash-Lite Preview 06-17      | 15  | 250,000 | 1,000  |
| Gemma 3 & 3n                               | 30  | 15,000  | 14,400 |

*   **RPM**: Requests Per Minute
*   **TPM**: Tokens Per Minute
*   **RPD**: Requests Per Day

### How to Get Multiple Gemini API Keys

Follow these steps to get the maximum number of free keys from a single Google account:

**Step 1: Open the Google Cloud Console**
*   Navigate to the [Google Cloud Console](https://console.cloud.google.com/). If you aren't logged in, you'll be prompted to do so.

**Step 2: Open the Project Picker**
*   In the top-left corner of the dashboard, you'll see a project name (e.g., "My First Project"). Click on it to open the project selection window.

**Step 3: Create Multiple Projects**
*   In the project selection window, click the **"New Project"** button.
*   Give the project any name you like (e.g., "TALKER-Key-1"). The name isn't important as you won't see it again.
*   Repeat this process until Google Cloud no longer allows you to create new projects (usually around 12).

**Step 4: Generate an API Key for Each Project**
**WARNING**: It is strongly recommended **not** to use your main Google account for creating API keys. There have been reports of accounts being affected, though the exact reasons are unclear. To be safe, create a separate, dedicated Google account for generating API keys.

*   Now, go to the [Google AI Studio API Key Page](https://aistudio.google.com/app/apikey).
*   Click the **"Create API key"** button.
*   A dropdown menu will appear. Select one of the projects you just created.
*   An API key will be generated. **Copy this key immediately.**

**Step 5: Add Keys to the Proxy**
*   Run the `setup_env.bat` script from the LLM-API-Key-Proxy.
*   Paste in the first Gemini API key you copied.
*   The script will ask if you want to add another key. Press `y` and then `Enter`.
*   Continue pasting in each new key you generate.

**Step 6: Repeat for All Projects**
*   Go back to the Google AI Studio page and repeat step 4 for all your projects, adding each new key to the proxy as you go. You can add all your keys in a single run of the `setup_env.bat` script.

**Step 7: Profit!**
*   You now have a pool of Gemini API keys. The proxy will automatically rotate through them, giving you a much higher free usage limit. You can even do this with multiple Google accounts for virtually unlimited use.

---

## 2. Chutes

> **<font color="red">IMPORTANT: Chutes is no longer a free service.</font>**
> To use their API, you must now make a **one-time payment of $5 to your account per API key**. This payment grants you **500 requests per day**, and the rate limit remains even if you use up the initial $5 credit.

Chutes offers a wide variety of models, but it's important to note that you can only generate one API key per account. However, you can create multiple accounts to obtain more keys.

**A Note on Rate Limits**: With the new paid structure, each key is limited to 500 requests per day.

### How to Get a Chutes API Key

**Step 1: Create an Account**
*   Go to [chutes.ai](https://chutes.ai/) and click **"Create Account"**.
*   Enter a username and follow the prompts.
*   **Important**: You will be given a `fingerprint.txt` file. Save this file or its contents somewhere safe, as it is your password. Or just save it's contents somewhere safe(password manager), as it is your password. You will not be able to log in without it.

**Step 2: Generate an API Key**
*   Log in to your new account and navigate to the [API section](https://chutes.ai/app/api).
*   Click **"Create API Key"** and copy the key that is generated.

**Step 3: Add the Key to the Proxy**
*   Run the `setup_env.bat` script from the LLM-API-Key-Proxy.
*   When prompted, paste in your Chutes API key.

**Step 4: (Optional) Create More Accounts for More Keys**
*   Chutes limits how frequently you can create new accounts from the same IP address. If you need more keys, you can use a private browsing window, Tor, or simply wait a while before creating another account.
*   Repeat the steps above for each new account and add each new key to the proxy.

**Step 5: Profit!**
*   You now have a pool of Chutes API keys. The proxy will automatically rotate through them, giving you a much higher free usage limit.

### Models and Performance

Chutes offers a wide range of models with varying performance. A general rule of thumb is that models with fewer billions (B) of parameters are faster but less intelligent. The speeds listed below are approximate and can change based on server load.

**Thinking Models**

| Model Name (Provider Prefix)                               | Relative Speed | Notes                                                                                                                                 |
| ---------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `chutes/NousResearch/DeepHermes-3-Mistral-24B-Preview`     | Very Fast      | An exceptionally fast model, great for quick reasoning.                                                                               |
| `chutes/Qwen/Qwen3-30B-A3B`                                | Very Fast           | A solid choice for dialogue and reasoning, though often outperformed by the latest DeepSeek and Llama models.                           |
| `chutes/microsoft/MAI-DS-R1-FP8`                           | Moderate-Fast       | Generally faster and better than the base DeepSeek-R1, but not as capable as the newer R1-0528 variant.                                  |
| `chutes/Qwen/Qwen3-32B`                                    | Moderate       | A decent all-arounder. Probably use A3B version instead                                                                                                                |
| `chutes/deepseek-ai/DeepSeek-R1`                           | Moderate       | A solid baseline reasoning model.                                                                                                     |
| `chutes/Qwen/Qwen3-235B-A22B`                              | Slow           | A very large model, which can be powerful but is often slower.                                                                        |
| `chutes/deepseek-ai/DeepSeek-R1-0528`                      | Slow           | The most capable version of DeepSeek-R1, but its performance can be very slow on Chutes.                                                 |

**Non-Thinking Models**

| Model Name (Provider Prefix)                               | Relative Speed | Notes                                                                                                                                 |
| ---------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `chutes/chutesai/Llama-4-Maverick-17B-128E-Instruct-FP8`   | Fast           | **Recommended for most non-thinking tasks.** A fast and reliable choice.                                                              |
| `chutes/google/gemma-3-27b-it`                             | Moderate       | A good fallback option.                                                                                                               |
| `chutes/deepseek-ai/DeepSeek-V3`                           | Moderate       | **Recommended for most non-thinking tasks.** A very capable and reliable model.                                                       |
| `chutes/chutesai/Llama-4-Scout-17B-16E-Instruct`           | Moderate           | A less powerful version of Llama 4.                                                                                                   |
| `chutes/deepseek-ai/DeepSeek-V3-0324`                      | Slow           | **Recommended for most non-thinking tasks.** A slightly different version of V3, newer and smarter, but its performance can be very slow on Chutes.                                   |

---

## 3. Nvidia

Nvidia offers an even wider selection of high-quality models than Chutes, making it a powerful option for experimentation. However, there are a few key limitations to keep in mind.

**Account and API Key Limitations**
*   You can only create one API key per Nvidia account.
*   Creating a new account requires phone number verification, which makes it difficult to acquire multiple keys.

**A Note on Rate Limits**
*   Like Chutes, Nvidia's rate limits are not officially published. They appear to be generous and dependent on server load, but it's always best to use the service reasonably.

### How to Get an Nvidia API Key

**Step 1: Create and Verify Your Account**
*   Go to [build.nvidia.com](https://build.nvidia.com/) and create a new account or log in to an existing one.
*   You will need to verify your account with a phone number and email address to proceed.

**Step 2: Generate Your API Key**
*   Once you are logged in, navigate to the main dashboard.
*   Click the **"Get API Key"** button to generate your unique key.

**Step 3: Add the Key to the Proxy**
*   Run the `setup_env.bat` script from the LLM-API-Key-Proxy.
*   When prompted, paste in your Nvidia API key.

### Available Models

Here are some of the notable models available through Nvidia's API:

| Model Name (Provider Prefix)                               | Notes                                                                                                                                      |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `nvidia_nim/nvidia/llama-3.1-nemotron-ultra-253b-v1`       | A massive, powerful model that excels at complex reasoning and dialogue. (Thinking model by default in the mod)                                |
| `nvidia_nim/meta/llama-4-maverick-17b-128e-instruct`        | Fast           | **Recommended for most non-thinking tasks.** A fast and reliable choice.                                                              |
| `nvidia_nim/nvidia/llama-3.3-nemotron-super-49b-v1`        | A smaller but still very capable version of Nemotron, offering a good balance of performance and intelligence. (Thinking model by default in the mod) |
| `nvidia_nim/deepseek-ai/deepseek-r1-0528`                  | The latest and most powerful version of DeepSeek-R1, excellent for reasoning tasks.                                                        |
| `nvidia_nim/deepseek-ai/deepseek-r1`                       | The base version of DeepSeek-R1, a solid all-arounder.                                                                                     |
| `nvidia_nim/qwen/qwen3-235b-a22b`                          | A very large model from the Qwen family, capable of high-quality output but may be slower. (Thinking model by default in the mod)             |
| `nvidia_nim/google/gemma-3-27b-it`                         | A powerful model from Google that is a great alternative to other options.                                                                 |
