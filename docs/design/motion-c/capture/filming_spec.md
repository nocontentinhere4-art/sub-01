# Filming spec for reference takes

These notes cover how to film reference clips that we measure with MediaPipe Pose (route (c)). The video is only measured. We use it to read root height and pitch over time, the hand and elbow targets, and the contact frames. The video itself never goes into the repo.

The notes come from the first measured clip, `idles/seat_leanback`. With stock footage, the torso and arms measured well. The legs were unusable because the desk and chair hid them.

## Camera
- **Angle: side-on**, 90° to the direction the person faces, for seated and lying actions. Turns, reaches across the body and anything with depth also need a **second take from the front three-quarter** (about 45°). Two separate takes are fine: we sync them on a clap.
- **Height: at the hips for seated takes** (about 70–90 cm) and **at the chest for standing takes** (about 110–130 cm). Keep the camera level, not tilted. Tilting down reads as forward lean in the numbers.
- **Distance: 2.5–4 m**, using the normal lens, not ultra-wide. Wide lenses bend the limbs near the frame edges.
- **The camera must not move.** Use a tripod or prop it on a shelf. No handheld, pan or zoom. Turn off phone stabilisation if possible.

## Framing
- **The whole body stays in frame for the whole take, including the feet and the top of the head**, with a margin of about 10%. Cut feet are the most common failure.
- **Nothing between the camera and the body.** For seated takes, put the camera on the side away from the desk, or pull the chair half out so the legs show. A chair with a thin frame or a low back is better than a high solid one.
- **Landscape, at least 1080p and 30 fps.** Use 60 fps for fast actions such as catching a falling bottle or flopping onto the bed.

## Light and background
- **Light should be even and bright and come from the front or side, never from behind the person.** Do not film against a window: backlight is the main cause of lost landmarks.
- **A plain background helps, but it isn't required.** What matters more is **contrast between clothes and background**. Don't wear dark clothes against a dark wall.
- **Fitted clothes.** A loose hoodie hides the shoulder and elbow. Sleeves pushed up are better. No logos.
- **No other people in frame.**

## Takes
- **Each take is one continuous shot. No cuts.** The measurement needs every frame of the motion.
- **Hold still for 2 s at the start and 2 s at the end**, in the base pose (seated upright at the desk, standing relaxed, and so on). This gives the clean start and end the loops need.
- **Length: 5–15 s for one action.** For idles (shifting weight, looking around), film 30–60 s of natural behaviour and we cut the pieces out.
- **Film 3 takes of each action.** We pick the cleanest, and the variation between takes gives the variants.
- **Real props, real furniture.** Drink from a real bottle, put a real bag on a desk at about the same height. Contact frames are read from the props.
- **Clap once in view at the start** when filming two angles.

## Privacy
- Faces are not needed. Turning away is fine, and so is a cap. Every frame we commit is anonymised (face pixelated), and the source video stays out of git.
- The performer must be an adult who agreed to be filmed.

## Priority list (most value first)
1. Seated: weight shift, look around, scratch, rub eyes, stretch, adjust hoodie, slow settle (one 60 s idle take covers most of these).
2. Seated drink from a bottle on the desk: grasp, drink, put down.
3. Standing idle sway, 60 s.
4. Phone: held standing and held lying on a bed.
5. Bag: pick it up at the door, carry it, put it on the desk.
6. Drop trash in a bin; lean on a window sill.
7. Lying: roll over as if asleep.
