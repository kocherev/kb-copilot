# Interface

Sources to read before changing UI:

- https://emilkowal.ski/skill
- https://jakubkurz.com/skills
- https://jakubkurz.com/writing/details-that-make-interfaces-feel-better

Rules for this app:

- New primitives come from https://ds.asanshay.com/ before Honest UI or a hand-rolled shadcn component.
- The homepage button is already copied from Honest UI. It lives in `apps/web/src/components/ui`, with tokens in `apps/web/src/styles/honest-ui-theme.css`. Leave that button in place. Set `data-theme` and `data-gray-color` on `html` so those tokens resolve.
- A control that can be pressed scales slightly on `:active` (about 0.97). The Honest UI button already does this. Do not remove it.
- Do not animate an element in from `scale(0)`. Start near its final size and fade.
- UI motion stays under 300ms. Enter and exit with a strong ease-out. Do not use `ease-in` for UI. Skip animation on actions people repeat all day.
- Popovers scale from the trigger. Modals stay centered.
- Show a focus ring on keyboard focus. Keep the coarse-pointer hit padding on buttons.
- Check empty text, one character, and a long unbroken string before calling a screen done.
- Say what the screen does. Do not add a second heading that restates the first.
