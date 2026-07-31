# Package G HAOS test checkpoint

Package G is the first user-visible Phase 2 checkpoint. It adds the local
Intelligent Climate sidebar while retaining the approved zero-physical-control
boundary. Use only an exact commit whose Quality, Hassfest, and HACS checks have
passed.

## Safety boundary

- Test only in **Observe Only** or **Scheduled Shadow**.
- The panel is read-only. It has no thermostat-control buttons, active adapter,
  physical sink, or Home Assistant service call.
- “Would have commanded” records describe suppressed Shadow decisions; they do
  not mean the thermostat was changed.
- Indoor prediction, planned-runtime, optimization, and model-ready claims are
  explicitly absent from this checkpoint.

## Before installation

1. Record the currently installed Intelligent Climate version and source
   commit, if shown by the installation method.
2. Create a Home Assistant backup that includes the `config` folder.
3. Save a copy of
   `/config/custom_components/intelligent_climate` outside that directory.
4. Confirm Intelligent Climate is in Observe Only or Scheduled Shadow.

## Install the verified candidate

1. Download the source archive for the exact verified Package G PR head.
2. Replace `/config/custom_components/intelligent_climate` with the archive's
   `custom_components/intelligent_climate` directory. Do not copy the repository
   root or the `frontend` source package into Home Assistant.
3. Restart Home Assistant.
4. Hard-refresh the browser once. The bundled panel URL is versioned, but a hard
   refresh also clears any stale shell state.
5. Select **Intelligent Climate** in the sidebar.

## Guided walkthrough

Verify the following without changing thermostat state:

1. **Overview** shows the correct equipment group, current control state, and an
   explicit “Automation is off” statement in Observe Only.
2. Zone temperature, humidity, target, HVAC action, and unavailable fields match
   existing Home Assistant entities; missing data is not displayed as zero.
3. **Shadow readiness** and “would have commanded” activity agree with the
   integration's current Shadow state.
4. The **Today** timeline uses the Home Assistant time zone, labels measured,
   configured, and calculated data distinctly, and describes any missing
   capability instead of inventing data.
5. **Sensors** identifies unavailable or excluded sources without exposing
   sensitive raw payloads.
6. **Activity** filters records without changing their chronological order.
7. **Settings** states that this checkpoint is read-only and directs
   configuration changes to supported Home Assistant surfaces.
8. Reload the integration, restart Home Assistant, refresh the browser, and
   switch light/dark themes. The panel should recover without duplicates.
9. At desktop, tablet, and narrow phone widths, route controls remain reachable
   and keyboard focus remains visible.

Capture the Home Assistant Core version, browser/device, screenshots, and any
console or integration log errors with the exact Package G commit.

## Rollback

1. Remove the Package G `intelligent_climate` directory.
2. Restore the saved prior
   `/config/custom_components/intelligent_climate` directory.
3. Restart Home Assistant and hard-refresh the browser.
4. Confirm existing Phase 1 entities and observations have returned. The
   Package G sidebar should no longer be registered.

Do not delete Intelligent Climate config entries or `.storage` files during
rollback.
