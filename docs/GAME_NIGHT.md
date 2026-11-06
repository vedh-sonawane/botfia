# Game-night checklist

Do these in order to start and run a game. This assumes setup is already done (see
docs/SETUP.md). Botfia is pass-and-play: one shared device goes around the circle.

## Before you start

1. Turn the Sony speaker on. Do this first so it reconnects to the Pi.
2. Plug in the Pi's power bank. Everything starts on boot, so just wait until the
   host screen is ready.
3. Power the ESP32 table unit from its USB charger. (If it never comes online, the
   game still runs — just without the eyes.)
4. Have the shared device ready. Any phone, tablet, or laptop works.

## Open the app

5. On the shared device, join the Pi's Wi-Fi and open `botfia.local`. If the name
   does not resolve, use the Pi's IP address shown on the host screen.
6. Check the host health panel: Wi-Fi, ESP32, speaker, Claude API, and light should
   all read OK. The game runs even if some are not, so this is just a heads-up.

## Set up the game

7. Enter player names in circle order — the order you will pass the device. This is
   the pass order, so get it right.
8. Set the options: role counts, discussion time, voting style (Secret or Open), and
   volumes. The defaults are fine for a first game.
9. Start.

## Role reveal

10. Pass the device around the circle. Each player presses and holds to see their
    role, then taps done and passes on. The role hides the instant they let go.
    Mafia also see their teammates. Do not peek at the person before you.

## Night

11. Botfia announces the night and the room light goes off; the eyes and smile come
    on. Pass the device around again. Everyone takes a turn and every turn looks and
    takes about the same time, so you cannot tell roles from timing.
12. A hand-off screen says who to pass to next. The next player presses and holds to
    begin. Never use back or swipe to see the previous screen.

## Morning and day

13. Light comes back on. Botfia says by name what happened overnight.
14. The discussion countdown runs. As host you can pause, add time, or skip from the
    host controls (behind a deliberate gesture so nobody hits them by accident).
15. Vote with the style you chose. Secret: pass the device and vote privately. Open:
    show of hands, host enters who was voted out. Botfia announces the result.

## End

16. Repeat night and day until a side wins. Botfia announces the winner and reveals
    every role, and the end screen summarizes what happened each night.
17. To play again, use restart in the host controls.
