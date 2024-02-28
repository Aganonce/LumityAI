<p align="center">
    <img src="/images/header.jpeg" alt="image" width="50%" height="auto">
</p>

## Integrating conversational AI and humans with an online game environment

Lumity provides an online game environment with an anonymous, live messaging system built in. The game is tooled toward debate and opinion consensus focused around a custom discussion prompt, with customizable player counts, time limits, and surveys sent out to players at the end of the game. Importantly, Lumity's primary feature is enabling the seamless integration of human players with conversational AI acting as players, allowing for Turing test-like situations. This program was built as part of a research initiative by RPI's NEST center [[1]](#references).

## Installation

Install requirements using

```bash
pip install -r requirements.txt
```

## Config file

All functionality is tied to the config file. Create a directory called `config` and add a YAML file within: `config/config.yml`

Here is a table of all the parameters that should be defined in the config file.

| Parameter | Description | Type |
| ----------- | ----------- | ----------- |
| host | The host of the MySQL database responsible for storing all data. | str |
| user | The user credentials of the MySQL database. | str |
| password | The password credentials of the MySQL database. | str |
| database | The MySQL database name. | str |
| prompt_id | The ID of the prompt being used in the current game. | int |
| gpt_4_secret_key | The secret key for the GPT-4 OpenAI API. | str |
| chatgpt_secret_key | A separate secret key for the ChatGPT OpenAI API. | str |
| llama_secret_key | Another separate secret key for Meta's LLAMA2, through Replicate's API. | str |
| player_count | The number of players that are allowed per game. This includes humans and bots. | int |
| password_length | The length of password that will be randomly generated for users at the beginning of the game. | int |
| sleep_time | Event delay times for bots to prevent overload. | float |
| conversion_reward | The number of points awarded to a participant for converting another participant. | int |
| majority_reward | The number of points awarded to all participants who hold the majority opinion at the end of the game. | int |
| time_limit | The amount of time in hours that the study will run. After this all participants will be logged out and the app will lock itself. | float |
| timezone | The timezone for which all timestamps will be set to, and which all time-related functionality will adhere to. Primarily use `US/Eastern` or `UTC`, but all valid timezones can be referenced by calling `pytz.all_timezones`.  | str |
| exit_survey_bots | URL pointing to the online exit survey for losing participants in a game that included bots. | str |
| exit_survey_humans | URL pointing to the online exit survey for losing participants in a game that included only humans. | str |
| exit_survey_bots_winner | URL pointing to the online exit survey for winning participants in a game that included bots. | str |
| exit_survey_humans_winner | URL pointing to the online exit survey for winning participants in a game that included only humans. | str |

## Database setup

There are seven primary tables that the database needs for the game to function. You can generate these tables by running

```sql
CREATE TABLE users (user_id INT PRIMARY KEY NOT NULL, username VARCHAR(255) NOT NULL, password VARCHAR(255) NOT NULL, points INT, bot BOOLEAN NOT NULL, email VARCHAR(255), created_at TIMESTAMP, notify BOOLEAN NOT NULL);
CREATE TABLE prompts (prompt_id INT PRIMARY KEY NOT NULL, prompt TEXT NOT NULL, opinions TEXT NOT NULL);
CREATE TABLE opinions (opinion_id INT PRIMARY KEY NOT NULL, prompt_id INT NOT NULL, user_id INT NOT NULL, conversation_id INT, created_at TIMESTAMP, opinion VARCHAR(255) NOT NULL, personal_confidence INT NOT NULL, percieved_confidence INT);
CREATE TABLE conversations (conversation_id INT PRIMARY KEY NOT NULL, creator_id INT NOT NULL, invited_id INT NOT NULL, created_at TIMESTAMP, completed BOOLEAN NOT NULL);
CREATE TABLE messages (message_id INT PRIMARY KEY NOT NULL, sender_id INT NOT NULL, reciever_id INT NOT NULL, conversation_id INT NOT NULL, message TEXT, flagged BOOLEAN NOT NULL, flag_report TEXT, created_at TIMESTAMP, login_action VARCHAR(255));
CREATE TABLE invites (invite_id INT PRIMARY KEY NOT NULL, sender_id INT NOT NULL, reciever_id INT NOT NULL, conversation_id INT NOT NULL, accepted BOOLEAN, rejected BOOLEAN, created_at TIMESTAMP, conversation_started BOOLEAN);
CREATE TABLE botcontext (bot_id INT NOT NULL, target_id INT NOT NULL, created_at TIMESTAMP, opinion VARCHAR(255) NOT NULL, primary key (bot_id, target_id));
```

To replicate the discussion prompt used in Lumity's research, run

```sql
INSERT INTO prompts (prompt_id, prompt, opinions) VALUES (1, "Which of these diets is the best compromise between nutritiousness and climate consciousness?", "1:Vegan|2:Vegetarian|3:Omnivorous|4:Pescatarian");
```

## Prompt engineering

The program `mod_utils.py` contains all of the prompts inputted into the conversational AI models during the game. These prompts must be adjusted based off the discussion prompt to enable the AI to act correctly during a game. The discussion prompt used in Lumity's research was: "Which of these diets is the best compromise between nutritiousness and climate consciousness?" Therefore, all vanilla prompts in `mod_utils.py` are geared toward this. Edit this program accordingly if the discussion prompt is changed. 

## Test app launch

To launch the online game interface on desktop for dev (to test UI), run

```bash
flet main.py -d
```

To launch the interface in a web browser, run

```bash
flet main.py -d -w
```

## Game setup and launch

Create directories for logging and for data storage. Run

```bash
mkdir logs data
```

You can launch a game by calling

```bash
python study_setup.py <NUM_HUMAN_PARTICIPANTS> <STUDY_ID>
```

Where `<NUM_HUMAN_PARTICIPANTS>` controls the number of human participants involved in the game and `<STUDY_ID>` defines the unique study ID for records (i.e., logging, data files). Run with the `-h` flag for more details. Upon launch this program will generate the login credentials for human players, and will instantiate and monitor all AI players. Once the time limit defined in the config file has expired, human players will be directed to the exit surveys, and all data involving invites, conversations, and aquired points will be dumped into the data directory.

## References

[1] Flamino, James, et al. "Limits of Large Language Models in Debating Humans." [arXiv preprint arXiv:2402.06049](https://arxiv.org/abs/2402.06049) (2024).
