# SERVER PROGRAM
# Main code for the user-facing Flet app, controls the UI of the game

import flet as ft
from time import sleep
import re
import random

from db_utils import *
from app_utils import *

class Message():
    def __init__(self, username: str, user_id: int, text: str, message_type: str):
        self.username = username
        self.user_id = user_id
        self.text = text
        self.message_type = message_type


class ChatMessage(ft.Row):
    def __init__(self, message: Message, page):
        super().__init__()
        self.message_type = message.message_type
        color_map = page.session.get('color_map')
        if self.message_type == "chat_message":
            self.vertical_alignment = "start"
            self.controls = [
                ft.CircleAvatar(
                    content=ft.Text(shorten_username(message.username)),
                    color=ft.colors.WHITE,
                    bgcolor=color_map[message.user_id],
                ),
                ft.Column(
                    [
                        ft.Text(message.username, weight="bold"),
                        ft.Container(
                            content=ft.Text(message.text, selectable=True),
                            width=page.width - 200 # NOTE: use this to adjust visible length of text messages in chat
                        )
                    ],
                    tight=True,
                    spacing=5,
                ),
            ]
        elif self.message_type == "login_message":
            self.controls = []
        elif self.message_type == "logout_message":
            self.controls = [
                ft.Text(message.text, italic=True,
                        color=ft.colors.WHITE, size=12)
            ]
        elif self.message_type == "logout_message_init":
            self.controls = [
                ft.Text(message.text, italic=True,
                        color=ft.colors.WHITE, size=12)
            ]


def rail_stages(page):
    sign_in_rail = ft.NavigationRailDestination(
        icon_content=ft.Icon(ft.icons.LOGIN_OUTLINED),
        selected_icon_content=ft.Icon(ft.icons.LOGIN),
        label="Sign In"
    )
    prompt_rail = ft.NavigationRailDestination(
        icon_content=ft.Icon(ft.icons.CREATE_OUTLINED),
        selected_icon_content=ft.Icon(ft.icons.CREATE),
        label="Prompt"
    )
    participants_rail = ft.NavigationRailDestination(
        icon_content=ft.Icon(ft.icons.PERSON_OUTLINED),
        selected_icon_content=ft.Icon(ft.icons.PERSON),
        label="Participants"
    )
    messages_rail = ft.NavigationRailDestination(
        icon_content=ft.Icon(ft.icons.MESSAGE_OUTLINED),
        selected_icon_content=ft.Icon(ft.icons.MESSAGE),
        label="Messages"
    )
    info_rail = ft.NavigationRailDestination(
        icon_content=ft.Icon(ft.icons.INFO_OUTLINED),
        selected_icon_content=ft.Icon(ft.icons.INFO),
        label="Info"
    )
    invite_rail = ft.NavigationRailDestination(
        icon_content=ft.Icon(ft.icons.EMAIL_OUTLINED),
        selected_icon_content=ft.Icon(ft.icons.EMAIL),
        label="Invites"
    )

    if page.session.contains_key("user_id"):
        user_id = page.session.get("user_id")
        sent_invites, recieved_invites = get_invites(user_id)
        page.session.set("sent_invites", sent_invites)
        page.session.set("recieved_invites", recieved_invites)

        prev_conversation_id = page.session.get("conversation_id")
        if prev_conversation_id != -1:
            creator_id, invited_id = get_current_conversation(
                prev_conversation_id)
        else:
            creator_id, invited_id = -1, -1

        non_repeat_recieved_invites = []
        for recieved_invite in recieved_invites:
            sender_id, sender_username, recieved_conversation_id = recieved_invite
            if creator_id != sender_id and invited_id != sender_id:
                non_repeat_recieved_invites.append(recieved_invite)

        if len(non_repeat_recieved_invites) > 0:
            invite_rail = ft.NavigationRailDestination(
                icon_content=ft.Icon(ft.icons.MARK_EMAIL_UNREAD_OUTLINED),
                selected_icon_content=ft.Icon(ft.icons.MARK_EMAIL_UNREAD),
                label="Invites"
            )

    rail_content = []
    if page.session.get("logged in") == False:
        rail_content = [sign_in_rail]
    else:
        if page.session.get("prompt answered") == False:
            rail_content = [prompt_rail]
        else:
            if page.session.get("conversation_id") == -1:
                rail_content = [info_rail, participants_rail, invite_rail]
            else:
                rail_content = [info_rail, participants_rail,
                                invite_rail, messages_rail]

    return rail_content


def prompt_view(revise_opinion, page):
    def prompt_submit(e):
        if radio_group.value == None or dropdown_group.value == None:
            open_dlg(e)
        else:
            e.control.content = ft.Container(content=ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')]), width=100)
            e.control.text = ''
            e.control.disabled = True
            page.session.set('loading lock', -2)
            page.update()

            opinion = radio_group.value
            user_id = page.session.get("user_id")
            personal_confidence = dropdown_group.value
            submit_opinion(opinion, personal_confidence, 'NULL', 'NULL', user_id)

            page.session.set("prompt answered", True)
            page.session.set("opinion", radio_group.value)
            page.session.set(
                "confidence", confidence_map(dropdown_group.value))

            e.control.content = None
            e.control.text = 'Submit'
            e.control.disabled = False
            page.update()
            page.session.set('loading lock', -1)

            page.go('/information')

    def revise_prompt_submit(e):
        if dropdown_group.value == None or percieved_dropdown_group.value == None:
            open_dlg(e)
        else:
            proceed = False
            if radio_group.disabled == False:
                if radio_group.value == None:
                    open_dlg(e)
                else:
                    opinion = radio_group.value
                    proceed = True
            else:
                opinion = page.session.get("opinion")
                proceed = True

            if proceed:
                e.control.content = ft.Container(content=ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')]), width=100)
                e.control.text = ''
                e.control.disabled = True
                page.session.set('loading lock', -2)
                page.update()

                conversation_id = page.session.get("conversation_id")

                user_id = page.session.get("user_id")

                personal_confidence = dropdown_group.value
                percieved_confidence = percieved_dropdown_group.value

                end_conversation(conversation_id)

                submit_opinion(opinion, personal_confidence,
                               percieved_confidence, conversation_id, user_id)

                try:
                    page.pubsub.unsubscribe_topic(str(conversation_id))
                except:
                    pass

                page.session.set("prompt answered", True)
                page.session.set("opinion", opinion)
                page.session.set("confidence", confidence_map(dropdown_group.value))
                page.session.set("conversation_id", -1)
                page.session.set("revise opinion", False)
                page.session.set('conversation ended', False)
                page.session.set('navigate to messages', False)

                participants = get_participants(user_id)
                page.session.set("participants", participants)

                e.control.content = None
                e.control.text = 'Submit'
                e.control.disabled = False
                page.update()
                page.session.set('loading lock', -1)

                page.go('/information')

    def open_dlg(e):
        missing_dlg.open = True
        page.update()

    def close_dlg(e):
        missing_dlg.open = False
        page.update()

    def revise_radio_change(e):
        if e.control.value == "yes":
            new_opinion_text.value = "Other options:"
            radio_group.disabled = True
            page.update()
        else:
            new_opinion_text.value = "New answer:"
            radio_group.disabled = False
            page.update()

    missing_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                      color=ft.colors.AMBER, size=40),
        content=ft.Text("Please fill out all inputs before hitting submit."),
        actions=[
            ft.TextButton("Okay", on_click=close_dlg)
        ],
    )

    prompt_text = ft.Text(page.session.get("prompt"),
                          size=24, weight=ft.FontWeight.W_500, selectable=True)

    radio_buttons = []
    for opinion_val, opinion_label in page.session.get("opinions"):
        radio_buttons.append(
            ft.Radio(value=opinion_label, label=opinion_label))
    radio_group = ft.RadioGroup(content=ft.Column(radio_buttons))

    dropdown_group = ft.Dropdown(
        label="How confident are you in your answer?",
        hint_text="Your confidence",
        options=[
            ft.dropdown.Option(key=1, text=confidence_map(1)),
            ft.dropdown.Option(key=2, text=confidence_map(2)),
            ft.dropdown.Option(key=3, text=confidence_map(3)),
            ft.dropdown.Option(key=4, text=confidence_map(4))
        ]
    )

    submit_button = ft.ElevatedButton(text='Submit', on_click=prompt_submit)

    if revise_opinion:
        prev_opinion = page.session.get("opinion")

        radio_buttons = []
        for opinion_val, opinion_label in page.session.get("opinions"):
            if opinion_label != prev_opinion:
                radio_buttons.append(
                    ft.Radio(value=opinion_label, label=opinion_label))
        radio_group = ft.RadioGroup(content=ft.Column(radio_buttons))

        radio_group.visible = True
        radio_group.disabled = True

        text_group = ft.Column([
            ft.Text("The prompt: " + page.session.get("prompt"),
                    size=20, weight=ft.FontWeight.W_400, selectable=True),
            ft.Text("Your previous answer: " + prev_opinion, size=18,
                    weight=ft.FontWeight.W_400, selectable=True),
            ft.Text("Do you want to keep your old answer?"),
            ft.RadioGroup(value="yes", content=ft.Column([
                ft.Radio(value="yes", label="Yes"),
                ft.Radio(value="no", label="No")]),
                on_change=revise_radio_change
            )
        ])

        new_opinion_text = ft.Text("Other options:")

        percieved_dropdown_group = ft.Dropdown(
            label="How confident did you feel your conversation partner was?",
            hint_text="Their confidence?",
            options=[
                ft.dropdown.Option(key=0, text=confidence_map(0)),
                ft.dropdown.Option(key=1, text=confidence_map(1)),
                ft.dropdown.Option(key=2, text=confidence_map(2)),
                ft.dropdown.Option(key=3, text=confidence_map(3)),
                ft.dropdown.Option(key=4, text=confidence_map(4))
            ]
        )

        revise_submit_button = ft.ElevatedButton(
            text='Submit update', on_click=revise_prompt_submit)

        # revise_group_container = ft.Column([text_group, new_opinion_text, radio_group, dropdown_group, percieved_dropdown_group, revise_submit_button], height=page.height - 100, width=float("inf"), scroll=ft.ScrollMode.ALWAYS, expand=True)

        revise_group = ft.ListView(
            expand=False,
            spacing=10,
            auto_scroll=False,
            controls=[text_group, new_opinion_text, radio_group, dropdown_group, percieved_dropdown_group, revise_submit_button]
        )

        revise_group_container = ft.Container(content=revise_group, height=page.height - 100, width=float("inf"))

        return [missing_dlg, revise_group_container]
                
    else:
        base_group = ft.ListView(
            expand=False,
            spacing=10,
            auto_scroll=False,
            controls=[prompt_text, radio_group, dropdown_group, submit_button]
        )

        base_group_container = ft.Container(content=base_group, height=page.height - 100, width=float("inf"))

        return [missing_dlg, base_group_container]


def sign_in_view(page):
    def sign_in_submit(e):
        if page.session.get("locked out") == False and page.session.get("loading lock") == -1:
            if username.value == '' or password.value == '':
                open_missing_dlg(e)
            else:
                submit_button.content = ft.Container(content=ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')]), width=100)
                submit_button.text = ''
                submit_button.disabled = True
                page.session.set('loading lock', -2)
                page.update()

                user_id, opinion, confidence, bot, _ = check_sign_in(
                    username.value, password.value)
                if user_id == -1:
                    submit_button.content = None
                    submit_button.text = 'Submit'
                    submit_button.disabled = False
                    page.update()
                    page.session.set('loading lock', -1)

                    open_wrong_dlg(e)
                else:
                    page.session.set("user_id", user_id)
                    page.session.set("username", username.value)
                    page.session.set("logged in", True)

                    missing_conversation_id = check_for_missing_opinions(
                        user_id)
                    if missing_conversation_id == -1:
                        page.session.set("conversation_id",
                                            check_for_conversation(user_id))

                        if opinion != None and confidence != None:
                            page.session.set("prompt answered", True)
                            page.session.set("opinion", opinion)
                            page.session.set(
                                "confidence", confidence_map(confidence))

                        submit_button.content = None
                        submit_button.text = 'Submit'
                        submit_button.disabled = False
                        page.update()
                        page.session.set('loading lock', -1)

                        page.go('')
                    else:
                        page.session.set("conversation_id",
                                            missing_conversation_id)
                        page.session.set("revise opinion", True)
                        page.session.set("prompt answered", True)

                        if opinion != None and confidence != None:
                            page.session.set("opinion", opinion)
                            page.session.set(
                                "confidence", confidence_map(confidence))

                        submit_button.content = None
                        submit_button.text = 'Submit'
                        submit_button.disabled = False
                        page.update()
                        page.session.set('loading lock', -1)

                        page.go('')

    def open_missing_dlg(e):
        missing_dlg.open = True
        page.update()

    def close_missing_dlg(e):
        missing_dlg.open = False
        page.update()

    def open_wrong_dlg(e):
        wrong_dlg.open = True
        page.update()

    def close_wrong_dlg(e):
        wrong_dlg.open = False
        page.update()

    def close_exit_dlg(e):
        exit_dlg.open = False
        page.update()

    missing_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                      color=ft.colors.AMBER, size=40),
        content=ft.Text("Please fill out all inputs before hitting submit."),
        actions=[
            ft.TextButton("Okay", on_click=close_missing_dlg)
        ],
    )

    wrong_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.ERROR_ROUNDED, color=ft.colors.RED, size=40),
        content=ft.Text(
            "Either username or password incorrect. Please try again."),
        actions=[
            ft.TextButton("Okay", on_click=close_wrong_dlg)
        ],
    )

    def highlight_link(e):
        e.control.style.color = ft.colors.BLUE
        e.control.update()

    def unhighlight_link(e):
        e.control.style.color = None
        e.control.update()

    won, url_link = False, 'https://www.google.com/'
    if page.session.contains_key('user_id'):
        won, url_link = get_exit_survey_url(page.session.get('user_id'))

        exit_actions = [ft.TextButton("Go to survey", url=url_link)]
        if won:
            exit_content = ft.Text(spans=[
                ft.TextSpan("The study has concluded. Congratulations! You were were one of the winners! Please follow this "),
                ft.TextSpan(
                    "link",
                    ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
                    url=url_link,
                    on_enter=highlight_link,
                    on_exit=unhighlight_link,
                ),
                ft.TextSpan(" to take the evaluation and exit survey, or click the 'Go to survey' button below. Completing these surveys are required for you to recieve your enhanced compensation.")
            ])
        else:
            exit_content = ft.Text(spans=[
                ft.TextSpan("The study has concluded. Thank you for participating! Please follow this "),
                ft.TextSpan(
                    "link",
                    ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
                    url=url_link,
                    on_enter=highlight_link,
                    on_exit=unhighlight_link,
                ),
                ft.TextSpan(" to take the evaluation and exit survey, or click the 'Go to survey' button below. Completing these surveys are required for you to recieve compensation.")
            ])
    else:
        exit_actions = [ft.TextButton("Okay", on_click=close_exit_dlg)]
        exit_content = ft.Text("The study has concluded. Please exit the application.")

    exit_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.EXIT_TO_APP, color=ft.colors.AMBER, size=40),
        content=exit_content,
        actions=exit_actions
    )

    username = ft.TextField(label="Username")
    password = ft.TextField(
        label="Password", password=True, can_reveal_password=True, on_submit=sign_in_submit
    )

    if page.session.get("locked out") == True:
        if page.session.contains_key('user_id'):
            submit_button = ft.ElevatedButton(text='Go to survey', url=url_link)
        else:
            submit_button = ft.ElevatedButton(text='Submit', disabled=True)
        exit_dlg.open = True
        page.update()
    else:
        submit_button = ft.ElevatedButton(text='Submit', on_click=sign_in_submit, disabled=page.session.get("locked out"))

    return [exit_dlg, wrong_dlg, missing_dlg, username, password, submit_button]


def information_view(page):
    def open_dlg(e):
        review_dlg.open = True
        page.update()

    def close_dlg(e):
        review_dlg.open = False
        page.update()

    def open_email_dlg(e):
        email_dlg.open = True
        page.update()

    def close_email_dlg(e):
        email_dlg.open = False
        page.update()

    def submit_email_click(e):
        if email_submit.data == 1:
            page.session.set("notify", True)
            update_email_notifications(page.session.get("user_id"), add=True)

            email_submit.text = "Unsubscribe"
            email_submit.data = 0

            email_btn.text = 'Unsubscribe from emails'

            email_txt.value = "You are subscribed to email updates with the email below. To unsubscribe, hit 'Unsubscribe'."
        elif email_submit.data == 0:
            page.session.set("notify", False)
            update_email_notifications(page.session.get("user_id"), add=False)

            email_submit.text = "Subscribe"
            email_submit.data = 1

            email_btn.text = 'Subscribe to emails'

            email_txt.value = "Email updates will keep you on top of messages and conversation invites when you are not logged in! Specifically, you will only reccieve an email if someone whom you are engaged in conversation logs in and access your messages (so you have an opportunity to log in as engage in live messaging) or if someone sends you an conversation invite or accepts your invite. If you want to recieve notifications that will be sent to the email address below, hit the 'Subscribe' button."

        email_dlg.open = False


        page.update()

    info_color_map = page.session.get('color_map')
    welcome = ft.Text(
        size=24,
        weight=ft.FontWeight.W_500,
        selectable=True,
        spans=[
            ft.TextSpan(
                "Hello, ",
            ),
            ft.TextSpan(
                page.session.get("username"),
                ft.TextStyle(weight=ft.FontWeight.BOLD, color=info_color_map[page.session.get("user_id")])
            )
        ]
    )
    
    # header2 = ft.Text("Rules", size=18, weight=ft.FontWeight.W_500, selectable=True, color='white')
    
    # body1 = ft.Text("Now that you have chosen an answer and rated your confidence in it given the prompt, the rules of the game are simple: for every other player you convince to change their answer to yours, you receive " + str(get_config_parameter('conversion_reward')) +  " point(s). However, upon the conclusion of the game, the players who hold the most popular answer will all receive " + str(get_config_parameter('majority_reward')) +  " point(s). IMPORTANT: The top TWO players with the most points both win! Accordingly, it is critical to figure out what answer will likely be most popular quickly, even if it is not what you originally chose. This is because an early adopter has an equal chance at winning the game! The strategy is to discern what answers have merit in becoming the most popular one in the end and deciding how to proceed from there. However, don't spend too much time strategizing! Each game has a time limit, which is indicated by the countdown timer on the top right-hand corner of the screen. Once the timer has reached zero, you will automatically be logged out and the game will have ended.", size=14, selectable=True, color='white')
    
    # header3 = ft.Text("Starting and ending conversations", size=18, weight=ft.FontWeight.W_500, selectable=True, color='white')
    
    # body2 = ft.Text("You can start a conversation with other players by navigating to the 'Participants' tab on the navigation rail. Once there you can open channels of communication with specific players by selecting the 'Send message' button next to a player's icon. If another player wants to start a conversation with you, an invite will show up in the 'Invites' tab (the mail icon will indicate if you have unopened invites).", size=14, selectable=True, color='white')
    
    # body3 = ft.Text("You have the option to accept or reject any invites. Importantly, you can only engage in one conversation at a time, so you must allocate your time wisely. Once a conversation has started, you will be unable to send or accept conversation invites.", size=14, selectable=True, color='white')
    
    # body4 = ft.Text("Once in a conversation, you will have access to the game's chatroom, which can be navigated to by selecting the 'Messages' tab on the navigation rail (the tab is only visible once a conversation has started). You can talk with the other player for as long as you like.", size=14, selectable=True, color='white')
    
    # body5 = ft.Text("Both you and your conversation partner can end the conversation at any time by hitting the red 'X' button on the bottom of the screen. Once a conversation has been terminated, no more messages can be sent, and both players must decide on if they want to keep their opinion or change it. Afterwards, you will be able to send and accept conversation invites again.", size=14, selectable=True, color='white')
    
    header2 = ft.Text("Rules", size=18, weight=ft.FontWeight.W_500, selectable=True, color='white')
    
    body1 = ft.Text("For the rules of the game, refer to the 'rules' channel of our Discord.", size=14, selectable=True, color='white')

    header4 = ft.Text("Review the prompt and your answer", size=18, weight=ft.FontWeight.W_500, selectable=True, color='white')
    
    body6 = ft.Text("If you want to review the prompt, your selected answer, and the confidence rating that you gave your answer, select the 'Review prompt' button on the bottom of the screen when you are in the 'Info' tab.", size=14, selectable=True, color='white')
    
    header5 = ft.Text("Having chatroom issues?", size=18, weight=ft.FontWeight.W_500, selectable=True, color='white')
    
    body7 = ft.Text("If you are currently messaging someone, and they have not responded in a while (but the conversation hasn't been ended by them), there is a chance that the live chat has become unresponsive. To fix this, you can either close the app and reopen it, or you can hit the refresh button at the top right-hand corner of the screen (which is only visible when you are in the chatroom). Hitting refresh will refresh the chatroom in-app, and should automatically fix any problem you have with messaging.", size=14, selectable=True, color='white')

    header6 = ft.Text("Still experiencing issues?", size=18, weight=ft.FontWeight.W_500, selectable=True, color='white')
    
    body8 = ft.Text("When in doubt, close the app, reopen it, and log back in! If that doesn't fix the issue, you can reach our team using Discord. To do this, message our Organizer bot. Start your message with '!troubleshoot' followed by a space and then a description of the issue you are facing. Our team will immediately investigate the issue you are describing and send a response to the troubleshoot channel of the Discord. This response will be public, including your description of the issue and our answer.", size=14, selectable=True, color='white')
    
    
    # rules = ft.Column(
    #     expand=True,
    #     spacing=10,
    #     scroll='AUTO',
    #     controls=[header2, body1, header4, body6, header5, body7, header6, body8],
    # )

    rules = ft.ListView(
        expand=True,
        spacing=10,
        auto_scroll=False,
        controls=[header2, body1, header4, body6, header5, body7, header6, body8]
    )

    rules_container = ft.Container(content=rules, bgcolor='#121212', height=page.height-200, padding=8, border_radius=8)

    review_dlg = ft.AlertDialog(
        title=ft.Text("Review Prompt, Answer, and Confidence"),
        content=ft.Text("Prompt: " + page.session.get("prompt") + "\nYour current answer: " +
                        page.session.get("opinion") + "\nYour current confidence: " + page.session.get("confidence"), selectable=True),
        actions=[
            ft.TextButton("Close", on_click=close_dlg)
        ],
    )

    email_val, notify_val = check_email(page.session.get("user_id"))
    page.session.set("notify", notify_val)

    if page.session.get('notify') == False:
        email_btn = ft.ElevatedButton(
            text='Subscribe to emails', on_click=open_email_dlg)
        email_txt = ft.Text("Email updates will keep you on top of messages and conversation invites when you are not logged in! Specifically, you will only reccieve an email if someone whom you are engaged in conversation logs in and access your messages (so you have an opportunity to log in as engage in live messaging) or if someone sends you an conversation invite or accepts your invite. If you want to recieve notifications that will be sent to the email address below, hit the 'Subscribe' button.", size=20, weight=ft.FontWeight.W_400)
        email_input = ft.TextField(
            value=email_val, disabled=True, border_color="black")
        email_submit = ft.ElevatedButton(
            text="Subscribe",
            on_click=lambda e: submit_email_click(e),
            data=1
        )
    else:
        email_btn = ft.ElevatedButton(
            text='Unsubscribe from emails', on_click=open_email_dlg)
        email_txt = ft.Text(
            "You are subscribed to email updates with the email below. To unsubscribe, hit 'Unsubscribe'.", size=20, weight=ft.FontWeight.W_400)
        email_input = ft.TextField(
            value=email_val, disabled=True, border_color="black")
        email_submit = ft.ElevatedButton(
            text="Unsubscribe",
            on_click=lambda e: submit_email_click(e),
            data=0
        )

    email_dlg = ft.AlertDialog(
        content=ft.Column([email_txt, email_input]),
        actions=[
            email_submit,
            ft.TextButton("Close", on_click=close_email_dlg)
        ],
    )

    review_btn = ft.ElevatedButton(text='Review prompt', on_click=open_dlg)

    return [email_dlg, review_dlg, welcome, rules_container, review_btn]


def participants_view(page):
    def open_warning_dlg(e):
        warning_dlg.open = True

        e.control.content = None
        e.control.text = 'Send message'
        e.control.disabled = False
        page.session.set('loading lock', -1)

        page.update()

    def close_warning_dlg(e):
        warning_dlg.open = False
        page.update()

    def message(e):
        if page.session.get('loading lock') == -1:
            if page.session.get('waiting for conversation start') == False:
                e.control.content = ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')])
                e.control.text = ''
                e.control.disabled = True

                page.session.set('loading lock', e.control.data)
                page.update()

                if page.session.get("conversation_id") == -1:
                    user_id = page.session.get("user_id")
                    reciever_id = e.control.data
                    send_invite(user_id, reciever_id, page.session.get("username"))

                    participants = get_participants(page.session.get("user_id"))
                    page.session.set("participants", participants)

                    sent_invites, recieved_invites = get_invites(user_id)
                    page.session.set("sent_invites", sent_invites)
                    page.session.set("recieved_invites", recieved_invites)
                else:
                    open_warning_dlg(e)
            else:
                e.control.content = ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')])
                e.control.text = ''
                e.control.disabled = True

                page.session.set('loading lock', e.control.data)
                page.update()

                reciever_id = e.control.data
                fake_pending_invites = page.session.get('fake pending invites')
                fake_pending_invites.append(reciever_id)
                page.session.set('fake pending invites', fake_pending_invites)

    user_id = page.session.get("user_id")

    invite_accepted, conversation_id = check_for_accepted_invite(user_id)
    if invite_accepted and page.session.get('navigate to messages') == False:
        page.session.set('waiting for conversation start', True)

    participants = get_participants(page.session.get("user_id"))
    page.session.set("participants", participants)

    sent_invites, recieved_invites = get_invites(user_id)
    page.session.set("sent_invites", sent_invites)
    page.session.set("recieved_invites", recieved_invites)

    recieved_invites_processed = []
    for recieved_invite in recieved_invites:
        recieved_invites_processed.append(recieved_invite[0])

    row_content = []
    for participant in participants:
        participant_user_id, username, is_available = participant

        if is_available:
            target_index = -1
            for i in range(len(sent_invites)):
                if sent_invites[i][0] == participant_user_id:
                    target_index = i
                    break

            if target_index != -1:
                participant_user_id, conversation_id, accepted = sent_invites[target_index]
                if not accepted:
                    chat_button = ft.ElevatedButton(
                        text="Pending invite", disabled=True)
                    participant_avatar = ft.CircleAvatar(
                        content=ft.Text(shorten_username(username)),
                        color=ft.colors.WHITE,
                        bgcolor=ft.colors.GREY_800,
                        tooltip="Awaiting invite accept from " + username
                    )
                else:
                    creator_id, invited_id = get_current_conversation(
                        conversation_id)
                    if participant_user_id == creator_id or participant_user_id == invited_id:
                        chat_button = ft.ElevatedButton(
                            text="See messages", disabled=True)
                        participant_avatar = ft.CircleAvatar(
                            content=ft.Text(shorten_username(username)),
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.GREY_800,
                            tooltip="Please conclude messages from " + username
                        )
                    else:
                        chat_button = ft.ElevatedButton(
                            text="See invites", disabled=True)
                        participant_avatar = ft.CircleAvatar(
                            content=ft.Text(shorten_username(username)),
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.GREY_800,
                            tooltip="See invites tab for invite from " + username
                        )
            elif participant_user_id in recieved_invites_processed:
                if page.session.get("conversation ended") == True:
                    chat_button = ft.ElevatedButton(
                        text="Pending invite", disabled=True)
                    participant_avatar = ft.CircleAvatar(
                        content=ft.Text(shorten_username(username)),
                        color=ft.colors.WHITE,
                        bgcolor=ft.colors.GREY_800,
                        tooltip="Please end current conversation before going to invites tab for invite from " + username
                    )
                else:
                    chat_button = ft.ElevatedButton(
                        text="See invites", disabled=True)
                    participant_avatar = ft.CircleAvatar(
                        content=ft.Text(shorten_username(username)),
                        color=ft.colors.WHITE,
                        bgcolor=ft.colors.GREY_800,
                        tooltip="See invites tab for invite from " + username
                    )
            else:
                fake_pending_invites = page.session.get('fake pending invites')

                if participant_user_id in fake_pending_invites:
                    chat_button = ft.ElevatedButton(
                        text="Pending invite", disabled=True)
                    participant_avatar = ft.CircleAvatar(
                        content=ft.Text(shorten_username(username)),
                        color=ft.colors.WHITE,
                        bgcolor=ft.colors.GREY_800,
                        tooltip="Awaiting invite accept from " + username
                    )
                else:
                    color_map = page.session.get('color_map')
                    chat_button = ft.ElevatedButton(text="Send message", color="white", bgcolor=color_map[participant_user_id], on_click=message, data=participant_user_id)
                    participant_avatar = ft.CircleAvatar(
                        content=ft.Text(shorten_username(username)),
                        color=ft.colors.WHITE,
                        bgcolor=color_map[participant_user_id],
                        tooltip="Send a message to " + username
                    )
        else:
            chat_button = ft.ElevatedButton(
                text="In conversation", disabled=True)
            participant_avatar = ft.CircleAvatar(
                content=ft.Text(shorten_username(username)),
                color=ft.colors.WHITE,
                bgcolor=ft.colors.GREY_800,
                tooltip="Cannot send message to " + username
            )

        item = ft.Column(col={"md": 4}, controls=[
            ft.Text(username, weight="bold"), ft.Row([participant_avatar, chat_button], tight=True, spacing=5,
                                                     )
        ])
        row_content.append(item)

    participant_list = ft.ResponsiveRow(row_content)

    page.session.set('participant_list', participant_list)
    page.session.set('message_func', message)

    warning_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                      color=ft.colors.AMBER, size=40),
        content=ft.Text("You are already in a conversation. Please navigate to the messages tab and select the 'End Conversation' button before sending more conversation invites from the participants tab."),
        actions=[
            ft.TextButton("Okay", on_click=close_warning_dlg)
        ],
    )

    return [warning_dlg, participant_list]


def invites_view(page):
    def join_messages(user_id, conversation_id):
        sent_invites, recieved_invites = get_invites(user_id)
        page.session.set("sent_invites", sent_invites)
        page.session.set("recieved_invites", recieved_invites)

        participants = get_participants(user_id)
        page.session.set("participants", participants)

        page.session.set("conversation_id", conversation_id)

        page.session.set('force enter conversation', True)
        page.go('/messages')

    def open_dlg(e):
        warning_dlg.open = True
        page.update()

    def close_dlg(e):
        warning_dlg.open = False
        page.update()

    def open_fail_dlg(e):
        failed_accept_dlg.open = True
        page.update()

    def close_fail_dlg(e):
        failed_accept_dlg.open = False

        user_id = page.session.get('user_id')
        sent_invites, recieved_invites = get_invites(user_id)
        page.session.set("sent_invites", sent_invites)
        page.session.set("recieved_invites", recieved_invites)

        page.views.clear()
        
        enter_messages_dlg, appbar_item = page.session.get('appbar item')
        view_list = [enter_messages_dlg, appbar_item]
        if page.route == "/prompts":
            view_list.append(route_view(page, "/"))
        elif page.route == "/participants":
            view_list.append(route_view(page, "/participants"))
        elif page.route == "/messages":
            view_list.append(route_view(page, "/messages"))
        elif page.route == "/information":
            view_list.append(route_view(page, "/information"))
        elif page.route == "/invites":
            view_list.append(route_view(page, "/invites"))
        else:
            view_list.append(route_view(page, "/"))
        page.views.append(ft.View(page.route, view_list))
        page.update()

    def reject(e):
        if page.session.get('loading lock') == -1:
            sender_id, conversation_id = e.control.data
            page.session.set('loading lock', conversation_id)

            e.control.content = ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')])
            e.control.text = ''
            e.control.disabled = True
            page.update()

            user_id = page.session.get("user_id")
            update_successful = update_invite(user_id, sender_id, conversation_id, False, False)

            sent_invites, recieved_invites = get_invites(user_id)
            page.session.set("sent_invites", sent_invites)
            page.session.set("recieved_invites", recieved_invites)

            page.update()

            page.session.set('loading lock', -1)

    def accept(e):
        if page.session.get('loading lock') == -1:
            if page.session.get("conversation_id") == -1:
                sender_id, conversation_id = e.control.data
                page.session.set('loading lock', conversation_id)

                user_id = page.session.get("user_id")

                e.control.content = ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')])
                e.control.text = ''
                e.control.disabled = True
                page.update()

                sleep(round(random.uniform(0, 3), 1))
                sleep(round(random.uniform(0, 3), 1))

                if not recheck_for_rejected_invite(conversation_id):
                    concurrent_invite_exists, new_conversation_id = check_for_concurrent_invite(user_id, sender_id, conversation_id)
                    if not concurrent_invite_exists:

                        update_successful = update_invite(user_id, sender_id, conversation_id, True, False)

                        if update_successful:
                            sent_invites, recieved_invites = get_invites(user_id)
                            page.session.set("sent_invites", sent_invites)
                            page.session.set("recieved_invites", recieved_invites)

                            participants = get_participants(user_id)
                            page.session.set("participants", participants)

                            page.session.set("conversation_id", conversation_id)

                            page.go('/messages')
                        else:
                            open_fail_dlg(e)
                    else:
                        join_messages(user_id, new_conversation_id)
                else:
                    if page.route != '/invites':
                        page.session.set('reload invite rejection', True)
                        page.go('/invites')
                    else:
                        invite_accepted, conversation_id = check_for_accepted_invite(user_id)

                        if invite_accepted:
                            join_messages(user_id, conversation_id)
                        else:
                            page.session.set('loading lock', -1)
                            open_fail_dlg(e)
            else:
                open_dlg(e)

    recieved_invites = page.session.get("recieved_invites")

    row_content = []
    color_map = page.session.get('color_map')
    for recieved_invite in recieved_invites:
        sender_id, sender_username, conversation_id = recieved_invite

        prev_conversation_id = page.session.get("conversation_id")
        if prev_conversation_id != -1:
            creator_id, invited_id = get_current_conversation(
                prev_conversation_id)
        else:
            creator_id, invited_id = -1, -1

        if creator_id != sender_id and invited_id != sender_id:
            if page.session.get('loading lock') == conversation_id:
                accept_button = ft.ElevatedButton(
                    content=ft.Row([ft.ProgressRing(width=15, height=15, stroke_width = 2), ft.Text(value='Loading...')]), color="white", bgcolor=ft.colors.GREEN, disabled=True, on_click=accept, data=(sender_id, conversation_id))
            else:
                accept_button = ft.ElevatedButton(
                    text="Accept invite", color="white", bgcolor=ft.colors.GREEN, on_click=accept, data=(sender_id, conversation_id))

            reject_button = ft.ElevatedButton(
                text="Reject invite", color="white", bgcolor=ft.colors.RED, on_click=reject, data=(sender_id, conversation_id))
            
            invite_avatar = ft.CircleAvatar(
                content=ft.Text(shorten_username(sender_username)),
                color=ft.colors.WHITE,
                bgcolor=color_map[sender_id],
                tooltip="Accept invite from " + sender_username
            )

            item = ft.Column(col={"md": 6}, controls=[
                ft.Text(sender_username, weight="bold"), ft.Row([invite_avatar, accept_button, reject_button], tight=True, spacing=5,
                                                                )
            ])
            row_content.append(item)

    invite_list = ft.ResponsiveRow(row_content)

    warning_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                      color=ft.colors.AMBER, size=40),
        content=ft.Text("You are already in a conversation. Please navigate to the messages tab and select the 'End Conversation' button (the red 'X' on the bottom left-hand corner) before you accept another conversation invite from the invites tab."),
        actions=[
            ft.TextButton("Okay", on_click=close_dlg)
        ],
    )

    failed_accept_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                      color=ft.colors.AMBER, size=40),
        content=ft.Text("This person joined a different conversation first, so you cannot start a conversation with them. Refreshing your invites..."),
        actions=[
            ft.TextButton("Okay", on_click=close_fail_dlg)
        ],
        on_dismiss=lambda e: close_fail_dlg(e)
    )

    if page.session.get('reload invite rejection'):
        page.session.set('reload invite rejection', False)

        user_id = page.session.get('user_id')
        invite_accepted, conversation_id = check_for_accepted_invite(user_id)
        if invite_accepted:
            join_messages(user_id, conversation_id)
        else:
            failed_accept_dlg.open = True
            page.update()

    page.session.set('invite_list', invite_list)
    page.session.set('accept_func', accept)
    page.session.set('reject_func', reject)

    return [warning_dlg, failed_accept_dlg, invite_list]


def message_view(page):
    def on_message(topic, message: Message):
        m = ChatMessage(message, page)
        chat.controls.append(m)
        page.update()

        force_exit = False
        for control in chat.controls:
            try:
                if control.message_type == "logout_message":
                    force_exit = True
                    break
            except:
                pass

        if force_exit:
            page.session.set('pubsub broken', False)
            page.session.set('bot thread running', False)
            new_message.disabled = True
            new_message_btn.disabled = True
            new_message.value = "Conversation ended. Please select 'X'."
            if not page.session.get('conversation ender'):
                end_dlg.open = True
                page.update()
            else:
                page.session.set('conversation ender', False)

    def close_dlg(e):
        end_dlg.open = False
        page.update()

    def close_blacklist_dlg(e):
        blacklist_dlg.open = False
        page.update()

    def close_force_enter_dlg(e):
        force_enter_dlg.open = False
        page.update()


    def send_message_click(e):
        if new_message.value != "":
            violation, blacklist = check_for_blacklist_words(new_message.value)

            if not violation:
                page.pubsub.send_all_on_topic(str(page.session.get("conversation_id")), Message(username=page.session.get(
                    "username"), user_id=page.session.get("user_id"), text=new_message.value, message_type="chat_message"))

                submit_messages(page.session.get("user_id"), page.session.get(
                    "conversation_id"), new_message.value, '', flagged=check_for_bot_keyword(new_message.value))
            else:
                blacklist_dlg.content = ft.Text("Please do not use derogatory language in your messages. Words such as \"" + ", ".join(blacklist) + "\" are not allowed. Your last message will not be sent.")
                blacklist_dlg.open = True

            new_message.value = ""
            new_message.focus()
            page.update()

    def end_conversation_click(e):
        page.session.set('conversation ender', True)

        page.pubsub.send_all_on_topic(str(conversation_id), Message(
            username=username, user_id=user_id, text=f"{username} has ended the chat.", message_type="logout_message"))

        submit_messages(page.session.get("user_id"), page.session.get(
            "conversation_id"), '', 'Ended conversation')

        page.session.set("viewed messages", False)

        page.session.set("prompt answered", False)

        page.session.set("revise opinion", True)

        page.go('/prompts')

    def update_rail():
        rail_stages_list = rail_stages(page)

        target_ind = -1
        for i, rail_item in enumerate(rail_stages_list):
            if rail_item.label == "Invites":
                target_ind = i
                break

        if target_ind != -1:
            rail_stages_list[target_ind].icon_content = ft.Icon(ft.icons.EMAIL_OUTLINED)
            rail_stages_list[target_ind].selected_icon_content=ft.Icon(ft.icons.EMAIL)

            rail = page.session.get('rail')
            rail.destinations = rail_stages_list
            page.update()

    conversation_id = page.session.get("conversation_id")
    username = page.session.get("username")
    user_id = page.session.get("user_id")

    user_id_username_map = page.session.get("user_id_username_map")
    reciever_id, prev_messages, bot = get_messages(user_id, conversation_id)
    reciever_username = user_id_username_map[reciever_id]

    reject_dangling_invites(user_id, conversation_id)
    update_rail()

    page.pubsub.subscribe_topic(str(conversation_id), on_message)

    if page.session.get('loading lock') == conversation_id:
        print('IN MESSAGES', page.session.get('loading lock'))
        page.session.set('loading lock', -1)

    chat = ft.ListView(
        expand=True,
        spacing=10,
        auto_scroll=True,
    )

    new_message = ft.TextField(
        hint_text="Write a message to " + reciever_username,
        autofocus=True,
        shift_enter=True,
        min_lines=1,
        max_lines=5,
        filled=True,
        expand=True,
        on_submit=send_message_click,
    )

    page.session.set('new_message', new_message)

    new_message_btn = ft.IconButton(
        icon=ft.icons.SEND_ROUNDED,
        tooltip="Send message to " + reciever_username,
        on_click=send_message_click
    )

    page.session.set('new_message_btn', new_message_btn)

    blacklist_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.REPORT_GMAILERRORRED,
                      color=ft.colors.RED, size=40),
        content=ft.Text(
            "Please do not use derogatory language in your messages. Your last message will not be sent."),
        actions=[
            ft.TextButton("Sorry", on_click=close_blacklist_dlg)
        ]
    )

    end_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED,
                      color=ft.colors.AMBER, size=40),
        content=ft.Text(
            reciever_username + " has terminated the conversation. Please select 'X' to review your prompt answer."),
        actions=[
            ft.TextButton("Okay", on_click=close_dlg)
        ]
    )

    force_enter_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.PLAY_CIRCLE,
                      color=ft.colors.GREEN, size=40),
        content=ft.Text(
            reciever_username + " has accepted your invite and started the conversation. Use the text box below to send messages."),
        actions=[
            ft.TextButton("Okay", on_click=close_force_enter_dlg)
        ]
    )

    def init_chatroom(prev_messages):
        for prev_message_row in prev_messages:
            sender_id, prev_message, prev_message_type = prev_message_row

            prev_username = user_id_username_map[sender_id]

            if prev_message_type == '':
                on_message(str(conversation_id), Message(username=prev_username,
                           user_id=sender_id, text=prev_message, message_type="chat_message"))
            elif prev_message_type == 'Ended conversation':
                on_message(str(conversation_id), Message(username=prev_username, user_id=sender_id,
                           text=f"{prev_username} has ended the chat.", message_type="logout_message_init"))

            if prev_message_type == "Ended conversation":
                new_message.disabled = True
                new_message_btn.disabled = True
                new_message_btn.tooltip = "Cannot send message to " + reciever_username
                new_message.value = "Conversation ended. Please select 'X'."

                page.session.set('conversation ended', True)
                page.session.set('pubsub broken', False)
                page.session.set('bot thread running', False)

                page.update()
                break

    if len(prev_messages) > 0:
        init_chatroom(prev_messages)

    page.session.set('chat', chat)

    if not page.session.get("revise opinion"):
        if not page.session.get("viewed messages"):
            if not page.session.get('conversation ended'):
                page.pubsub.send_all_on_topic(str(conversation_id), Message(
                    username=username, user_id=user_id, text=f"{username} has joined the chat.", message_type="login_message"))
                submit_messages(page.session.get("user_id"), page.session.get(
                    "conversation_id"), '', 'Logged in')
                page.session.set("viewed messages", True)
        else:
            on_message(str(conversation_id), Message(username=username, user_id=user_id,
                       text=f"{username} has joined the chat.", message_type="login_message"))


    if bot == 1 and page.session.get('bot thread running') == False:
        if page.session.get('conversation ended') == False:
            reciever_id, current_messages, bot = get_messages(page.session.get('user_id'), page.session.get('conversation_id'))
            page.session.set('prev_messages', current_messages)
            page.session.set('bot thread running', True)

    if page.session.get('force enter conversation') == True:
        page.session.set('force enter conversation', False)
        force_enter_dlg.open = True
        page.update()


    message_content = [
        force_enter_dlg,
        end_dlg,
        blacklist_dlg,
        ft.Container(
            content=chat,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=5,
            padding=10,
            expand=True,
        ),
        ft.Row(
            [
                ft.IconButton(
                    icon=ft.icons.CLOSE_ROUNDED,
                    icon_color="red",
                    icon_size=20,
                    tooltip="End conversation",
                    on_click=end_conversation_click
                ),
                new_message,
                new_message_btn
            ]
        )
    ]

    # page.on_route_change = thread.exit()
    return message_content

def route_view(page, route):
    page.session.set('load in refresh', False)
    # print(route)

    rail_stages_list = rail_stages(page)
    if len(rail_stages_list) > 1:
        rail = ft.NavigationRail(
            selected_index=route_index_map(route),
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=400,
            group_alignment=-0.9,
            destinations=rail_stages_list,
            on_change=lambda e: page.go(
                index_route_map(e.control.selected_index)),
            disabled=True
        )
    else:
        rail = ft.NavigationRail(
            selected_index=route_index_map(route),
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=400,
            group_alignment=-0.9,
            destinations=rail_stages_list,
            disabled=True
        )

    page.session.set('rail', rail)

    page_content = [ft.Text("Body of " + route)]

    if page.session.get("logged in") == False:
        page_content = sign_in_view(page)
    else:
        if route == '/':
            if page.session.get("prompt answered") == False:
                revise_opinion = page.session.get("revise opinion")

                page_content = prompt_view(revise_opinion, page)
            else:
                page_content = information_view(page)
        elif route == '/prompts':
            revise_opinion = page.session.get("revise opinion")

            page_content = prompt_view(revise_opinion, page)
        elif route == '/participants':
            page_content = participants_view(page)
        elif route == '/messages':
            page_content = message_view(page)
        elif route == '/invites':
            page_content = invites_view(page)
        elif route == '/information':
            page_content = information_view(page)

    rail_container = ft.Row(
        [
            rail,
            ft.VerticalDivider(width=1),
            ft.Column(page_content,
                      alignment=ft.MainAxisAlignment.START, expand=True),
        ],
        expand=True,
    )

    return rail_container

def appbar_view(page):
    def close_enter_messages_dlg(e):
        page.session.set('navigate to messages', True)
        page.session.set('waiting for conversation start', False)
        page.session.set('fake pending invites', [])
        enter_messages_dlg.open = False
        page.update()

    def refresh_click(e):
        if page.route == "/messages":
            reciever_id, current_messages, bot = get_messages(page.session.get('user_id'), page.session.get('conversation_id'))
            page.session.set('prev_messages', current_messages)

            page.session.set('pubsub broken', True)

            page.views.clear()

            enter_messages_dlg, appbar_item = page.session.get('appbar item')
            view_list = [enter_messages_dlg, appbar_item]
            if page.route == "/prompts":
                view_list.append(route_view(page, "/"))
            elif page.route == "/participants":
                view_list.append(route_view(page, "/participants"))
            elif page.route == "/messages":
                view_list.append(route_view(page, "/messages"))
            elif page.route == "/information":
                view_list.append(route_view(page, "/information"))
            elif page.route == "/invites":
                view_list.append(route_view(page, "/invites"))
            else:
                view_list.append(route_view(page, "/"))
            page.views.append(ft.View(page.route, view_list))
            page.update()

    enter_messages_dlg = ft.AlertDialog(
        title=ft.Icon(ft.icons.PLAY_CIRCLE,
                      color=ft.colors.GREEN, size=40),
        content=ft.Text(
            "Someone has accepted your invite and started the conversation. Click the 'Messages' tab to talk to them."),
        actions=[
            ft.TextButton("Okay", on_click=close_enter_messages_dlg)
        ],
        on_dismiss=lambda e: close_enter_messages_dlg(e),
    )

    appbar_action = []

    timer_text = ft.Text("00:00:00", size=20, weight=ft.FontWeight.W_500, selectable=False, color='red')
    appbar_action.append(timer_text)

    refresh_button = ft.IconButton(ft.icons.TIMER, disabled=True)
    
    appbar_action.append(refresh_button)

    appbar = ft.AppBar(
        leading=ft.Icon(ft.icons.TEXT_SNIPPET),
        leading_width=40,
        title=ft.Text('Lumity Engine'),
        center_title=False,
        bgcolor=ft.colors.SURFACE_VARIANT,
        actions=appbar_action
    )

    def dynamic_load(page): 
        def hot_join_messages(user_id, conversation_id):
            sent_invites, recieved_invites = get_invites(user_id)
            page.session.set("sent_invites", sent_invites)
            page.session.set("recieved_invites", recieved_invites)

            participants = get_participants(user_id)
            page.session.set("participants", participants)

            page.session.set("conversation_id", conversation_id)

        def hot_reload_chatroom(user_id, conversation_id):
            reciever_id, current_messages, bot = get_messages(user_id, conversation_id)

            user_id_username_map = page.session.get('user_id_username_map')
            reciever_username = user_id_username_map[reciever_id]

            if len(current_messages) == len(page.session.get('prev_messages')):
                print("same messages as before")
            else:
                page.session.set('prev_messages', current_messages)

                print("not same, updating messages...")

                new_message_list = []
                for message_row in current_messages:
                    sender_id, prev_message, prev_message_type = message_row

                    prev_username = user_id_username_map[sender_id]

                    if prev_message_type == '':
                        new_message_list.append(Message(username=prev_username,
                                user_id=sender_id, text=prev_message, message_type="chat_message"))
                    elif prev_message_type == 'Ended conversation':
                        new_message_list.append(Message(username=prev_username, user_id=sender_id,
                                text=f"{prev_username} has ended the chat.", message_type="logout_message_init"))

                    if prev_message_type == "Ended conversation":
                        new_message = page.session.get('new_message')
                        new_message_btn = page.session.get('new_message_btn')

                        new_message.disabled = True
                        new_message_btn.disabled = True
                        new_message_btn.tooltip = "Cannot send message to " + reciever_username
                        new_message.value = "Conversation ended. Please select 'X'."
                        
                        page.session.set('conversation ended', True)
                        page.session.set('pubsub broken', False)
                        page.session.set('bot thread running', False)

                        page.update()
                        break

                if len(new_message_list) > 0:
                    chat = page.session.get('chat')

                    chat.controls = []
                    for message in new_message_list:
                        chat.controls.append(ChatMessage(message, page))
                    
                    page.update()

        def hot_reload_invites(sender_id, conversation_id, sender_username):
            color_map = page.session.get('color_map')

            accept_button = ft.ElevatedButton(
                text="Accept invite", color="white", bgcolor=ft.colors.GREEN, on_click=page.session.get('accept_func'), data=(sender_id, conversation_id))
            reject_button = ft.ElevatedButton(
                text="Reject invite", color="white", bgcolor=ft.colors.RED, on_click=page.session.get('reject_func'), data=(sender_id, conversation_id))
            invite_avatar = ft.CircleAvatar(
                content=ft.Text(shorten_username(sender_username)),
                color=ft.colors.WHITE,
                bgcolor=color_map[sender_id],
                tooltip="Accept invite from " + sender_username
            )

            item = ft.Column(col={"md": 6}, controls=[
                ft.Text(sender_username, weight="bold"), ft.Row([invite_avatar, accept_button, reject_button], tight=True, spacing=5,
                                                                )
            ])

            return item

        def hot_reload_participants():
            participants = get_participants(page.session.get("user_id"))

            sent_invites, recieved_invites = get_invites(user_id)

            recieved_invites_processed = []
            for recieved_invite in recieved_invites:
                recieved_invites_processed.append(recieved_invite[0])

            row_content = []
            for participant in participants:
                participant_user_id, username, is_available = participant

                if is_available:
                    target_index = -1
                    for i in range(len(sent_invites)):
                        if sent_invites[i][0] == participant_user_id:
                            target_index = i
                            break

                    if target_index != -1:
                        participant_user_id, conversation_id, accepted = sent_invites[target_index]
                        if not accepted:
                            chat_button = ft.ElevatedButton(
                                text="Pending invite", disabled=True)
                            participant_avatar = ft.CircleAvatar(
                                content=ft.Text(shorten_username(username)),
                                color=ft.colors.WHITE,
                                bgcolor=ft.colors.GREY_800,
                                tooltip="Awaiting invite accept from " + username
                            )
                        else:
                            creator_id, invited_id = get_current_conversation(
                                conversation_id)
                            if participant_user_id == creator_id or participant_user_id == invited_id:
                                chat_button = ft.ElevatedButton(
                                    text="See messages", disabled=True)
                                participant_avatar = ft.CircleAvatar(
                                    content=ft.Text(shorten_username(username)),
                                    color=ft.colors.WHITE,
                                    bgcolor=ft.colors.GREY_800,
                                    tooltip="Please conclude messages from " + username
                                )
                            else:
                                chat_button = ft.ElevatedButton(
                                    text="See invites", disabled=True)
                                participant_avatar = ft.CircleAvatar(
                                    content=ft.Text(shorten_username(username)),
                                    color=ft.colors.WHITE,
                                    bgcolor=ft.colors.GREY_800,
                                    tooltip="See invites tab for invite from " + username
                                )
                    elif participant_user_id in recieved_invites_processed:
                        if page.session.get("conversation ended") == True:
                            chat_button = ft.ElevatedButton(
                                text="Pending invite", disabled=True)
                            participant_avatar = ft.CircleAvatar(
                                content=ft.Text(shorten_username(username)),
                                color=ft.colors.WHITE,
                                bgcolor=ft.colors.GREY_800,
                                tooltip="Please end current conversation before going to invites tab for invite from " + username
                            )
                        else:
                            chat_button = ft.ElevatedButton(
                                text="See invites", disabled=True)
                            participant_avatar = ft.CircleAvatar(
                                content=ft.Text(shorten_username(username)),
                                color=ft.colors.WHITE,
                                bgcolor=ft.colors.GREY_800,
                                tooltip="See invites tab for invite from " + username
                            )
                    else:
                        fake_pending_invites = page.session.get('fake pending invites')

                        if participant_user_id in fake_pending_invites:
                            chat_button = ft.ElevatedButton(
                                text="Pending invite", disabled=True)
                            participant_avatar = ft.CircleAvatar(
                                content=ft.Text(shorten_username(username)),
                                color=ft.colors.WHITE,
                                bgcolor=ft.colors.GREY_800,
                                tooltip="Awaiting invite accept from " + username
                            )
                        else:
                            color_map = page.session.get('color_map')
                            
                            chat_button = ft.ElevatedButton(text="Send message", color="white", bgcolor=color_map[participant_user_id], on_click=page.session.get('message_func'), data=participant_user_id)
                            participant_avatar = ft.CircleAvatar(
                                content=ft.Text(shorten_username(username)),
                                color=ft.colors.WHITE,
                                bgcolor=color_map[participant_user_id],
                                tooltip="Send a message to " + username
                            )
                else:
                    chat_button = ft.ElevatedButton(
                        text="In conversation", disabled=True)
                    participant_avatar = ft.CircleAvatar(
                        content=ft.Text(shorten_username(username)),
                        color=ft.colors.WHITE,
                        bgcolor=ft.colors.GREY_800,
                        tooltip="Cannot send message to " + username
                    )

                item = ft.Column(col={"md": 4}, controls=[
                    ft.Text(username, weight="bold"), ft.Row([participant_avatar, chat_button], tight=True, spacing=5,
                                                            )
                ])
                row_content.append(item)
            
            return row_content
        
        def hot_reload_messages_tab(user_id):
            invite_accepted, conversation_id = check_for_accepted_invite(user_id)
            if invite_accepted:
                if page.session.get('navigate to messages') == False:
                    hot_join_messages(user_id, conversation_id)
                    rail_stages_list = rail_stages(page)

                    if rail_stages_list[-1].label != "Messages":
                        messages_rail = ft.NavigationRailDestination(
                            icon_content=ft.Icon(ft.icons.MESSAGE_OUTLINED),
                            selected_icon_content=ft.Icon(ft.icons.MESSAGE),
                            label="Messages"
                        )

                        rail_stages_list.append(messages_rail)

                    rail = page.session.get('rail')
                    rail.destinations = rail_stages_list

                    reciever_id, prev_messages, bot = get_messages(user_id, conversation_id)
                    user_id_username_map = page.session.get('user_id_username_map')
                    reciever_username = user_id_username_map[reciever_id]

                    enter_messages_dlg, appbar_item = page.session.get('appbar item')
                    enter_messages_dlg.content = ft.Text(reciever_username + " has accepted your invite and started the conversation. Click the 'Messages' tab to talk to them.")
                    enter_messages_dlg.open = True

                    page.update()

        def hot_reload_participant_invite_tabs(user_id):
            if page.route == "/participants":
                if page.session.contains_key('participant_list') and page.session.contains_key('message_func'):
                    sleep(2)

                    participant_list = page.session.get('participant_list')
                    participant_items = hot_reload_participants()
                    participant_list.controls = participant_items
                    page.update()

                    page.session.set('loading lock', -1)

            if page.session.get('loading lock') == -1:
                rail_stages_list = rail_stages(page)

                target_ind = -1
                for i, rail_item in enumerate(rail_stages_list):
                    if rail_item.label == "Invites":
                        target_ind = i
                        break

                if target_ind != -1:
                    sent_invites, recieved_invites = get_invites(user_id)

                    prev_conversation_id = page.session.get("conversation_id")
                    if prev_conversation_id != -1:
                        creator_id, invited_id = get_current_conversation(
                            prev_conversation_id)
                    else:
                        creator_id, invited_id = -1, -1

                    non_repeat_recieved_invites = []
                    for recieved_invite in recieved_invites:
                        sender_id, sender_username, recieved_conversation_id = recieved_invite
                        if creator_id != sender_id and invited_id != sender_id:
                            non_repeat_recieved_invites.append(recieved_invite)

                    if len(non_repeat_recieved_invites) > 0:
                        rail_stages_list[target_ind].icon_content = ft.Icon(ft.icons.MARK_EMAIL_UNREAD_OUTLINED)
                        rail_stages_list[target_ind].selected_icon_content=ft.Icon(ft.icons.MARK_EMAIL_UNREAD)
                    else:
                        rail_stages_list[target_ind].icon_content = ft.Icon(ft.icons.EMAIL_OUTLINED)
                        rail_stages_list[target_ind].selected_icon_content=ft.Icon(ft.icons.EMAIL)

                    rail = page.session.get('rail')
                    rail.destinations = rail_stages_list
                    page.update()

                    if page.route == "/invites":
                        sleep(1)
                        if page.session.get('loading lock') == -1:
                            print('trigger')
                            if page.session.contains_key('invite_list') and page.session.contains_key('accept_func') and page.session.contains_key('reject_func'):
                                row_content = []
                                for recieved_invite in recieved_invites:
                                    sender_id, sender_username, conversation_id = recieved_invite

                                    if creator_id != sender_id and invited_id != sender_id:
                                        item = hot_reload_invites(sender_id, conversation_id, sender_username)
                                        row_content.append(item)

                                invite_list = page.session.get('invite_list')

                                invite_list.controls = row_content
                                page.session.set('invite_list', invite_list)

                                page.update()

        tick = 1
        while tick:
            if page.session.get('logged in') == True and page.session.get('prompt answered') == True:
                if page.session.get('load in refresh') == False:
                    page.session.set('load in refresh', True)
                    if page.route == "/messages":
                        appbar.actions[-1] = ft.IconButton(ft.icons.REFRESH, on_click=refresh_click)
                    else:
                        appbar.actions[-1] = ft.IconButton(ft.icons.TIMER, disabled=True)
                    page.update()

                if page.route == "/messages":
                    if page.session.get('pubsub broken') == True or page.session.get('bot thread running') == True:
                        if page.session.contains_key('chat'):
                            sleep(1)
                            user_id = page.session.get('user_id')
                            conversation_id = page.session.get('conversation_id')
                            hot_reload_chatroom(user_id, conversation_id)
                else:
                    if page.session.contains_key("user_id"):
                        user_id = page.session.get('user_id')
                        hot_reload_messages_tab(user_id)
                        hot_reload_participant_invite_tabs(user_id)
                                
            
                page.update()
            sleep(100/1000)
            tick += 1

            if page.session.get('locked out') == True:
                break

        print('Dynamic loading ended')

    def countdown(t, page): 
        title_check = True
        while t:
            mins, secs = divmod(t, 60)
            hours, mins = divmod(mins, 60) # divide number of minutes by 60 to get hours
            timer_print = '{:02d}:{:02d}:{:02d}'.format(hours, mins, secs) 

            if t <= 60:
                timer_print_text = ft.Text(timer_print, size=20, weight=ft.FontWeight.W_500, selectable=False, color='red')
            else:
                timer_print_text = ft.Text(timer_print, size=20, weight=ft.FontWeight.W_500, selectable=False)

            if t % 60 == 0:
                if page.session.contains_key('user_created_at'):
                    if t > 0:
                        user_created_at, time_limit = page.session.get('user_created_at')
                        t = quick_timer_update(user_created_at, time_limit)
                        if t <= 0:
                            break

            appbar_action[0] = timer_print_text

            if title_check:
                if page.session.contains_key("username") and page.session.contains_key("user_id"):
                    title_check = False
                    timer_color_map = page.session.get('color_map')
                    appbar.title = ft.Text(
                        size=22,
                        spans=[
                            ft.TextSpan(
                                "Lumity Engine (",
                            ),
                            ft.TextSpan(
                                page.session.get("username"),
                                ft.TextStyle(weight=ft.FontWeight.BOLD, color=timer_color_map[page.session.get("user_id")])
                            ),
                            ft.TextSpan(
                                ")",
                            ),
                        ]
                    )


            
            page.update()
            time.sleep(1) 
            t -= 1

        appbar_action[0] = ft.Text('00:00:00', size=20, weight=ft.FontWeight.W_500, selectable=False, color='red')
        page.update()
        time.sleep(2)

        page.session.set('logged in', False)
        page.session.set("locked out", True)
        page.views.clear()
        enter_messages_dlg, appbar_item = page.session.get('appbar item')
        view_list = [enter_messages_dlg, appbar_item]
        view_list.append(route_view(page, "/"))
        page.views.append(ft.View("/", view_list))
        page.update()

    if page.session.get("start timer") == False:
        page.session.set("start timer", True)
        t, user_created_at, time_limit = get_timer_time()
        page.session.set('user_created_at', (user_created_at, time_limit))
        # t = 90
        if t > 0:
            thread = threading.Thread(target=countdown, args=[t, page])
            thread.start()
        else:
            page.session.set("locked out", True)

        if page.session.get('locked out') == False:
            thread = threading.Thread(target=dynamic_load, args=[page])
            thread.start()

    return (enter_messages_dlg, appbar)


def main(page: ft.Page):
    page.title = "Lumity Engine"

    page.session.set("logged in", False)
    page.session.set("locked out", False)
    page.session.set("viewed messages", False)
    page.session.set("prompt answered", False)
    page.session.set("revise opinion", False)
    page.session.set("notify", False)
    page.session.set("conversation_id", -1)
    page.session.set('conversation ended', False)
    page.session.set('force enter conversation', False)
    page.session.set('navigate to messages', False)
    page.session.set('bot thread running', False)
    page.session.set('start timer', False)
    page.session.set('loading lock', -1)
    page.session.set('reload invite rejection', False)
    page.session.set('conversation ender', False)
    page.session.set('load in refresh', False)
    page.session.set('pubsub broken', False)
    page.session.set("user_id_username_map", get_user_id_username_mapping())
    page.session.set('color_map', get_color_map(get_user_id_username_mapping()))

    page.session.set('prev_messages', [])

    page.session.set('waiting for conversation start', False)
    page.session.set('fake pending invites', [])

    prompt, opinions = get_prompt()
    page.session.set("prompt", prompt)
    page.session.set("opinions", opinions)

    page.session.set('appbar item', appbar_view(page))

    def route_change(route):
        page.views.clear()

        enter_messages_dlg, appbar_item = page.session.get('appbar item')
        view_list = [enter_messages_dlg, appbar_item]
        if page.route == "/prompts":
            view_list.append(route_view(page, "/"))
        elif page.route == "/participants":
            view_list.append(route_view(page, "/participants"))
        elif page.route == "/messages":
            view_list.append(route_view(page, "/messages"))
        elif page.route == "/information":
            view_list.append(route_view(page, "/information"))
        elif page.route == "/invites":
            view_list.append(route_view(page, "/invites"))
        else:
            view_list.append(route_view(page, "/"))
        page.views.append(ft.View(route, view_list))
        page.update()

    def view_pop(view):
        try:
            page.views.pop()
            top_view = page.views[-1]
            page.go(top_view.route)
        except:
            page.views.clear()

            enter_messages_dlg, appbar_item = page.session.get('appbar item')
            view_list = [enter_messages_dlg, appbar_item]
            if page.route == "/prompts":
                view_list.append(route_view(page, "/"))
            elif page.route == "/participants":
                view_list.append(route_view(page, "/participants"))
            elif page.route == "/messages":
                view_list.append(route_view(page, "/messages"))
            elif page.route == "/information":
                view_list.append(route_view(page, "/information"))
            elif page.route == "/invites":
                view_list.append(route_view(page, "/invites"))
            else:
                view_list.append(route_view(page, "/"))
            page.views.append(ft.View('/messages', view_list))
            page.update()

    def client_exited(e):
        page.pubsub.unsubscribe_all()

    def page_resize(e):
        route_change(page.route)

    page.on_resize = page_resize

    page.on_close = client_exited

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)


ft.app(port=8550, target=main, view=ft.WEB_BROWSER)
