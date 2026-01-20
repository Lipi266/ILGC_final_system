# ILGC Workplace Monitor - Testing Checklist

Use this checklist when testing the application before release.

## Build Testing

### macOS Build
- [ ] `build.sh` runs without errors
- [ ] Virtual environment created successfully
- [ ] Python dependencies installed
- [ ] pylsl library copied correctly
- [ ] Frontend builds successfully (dist/ created)
- [ ] PyInstaller creates .app bundle
- [ ] DMG installer created
- [ ] DMG opens and shows app + Applications link

### Windows Build
- [ ] `build.bat` runs without errors
- [ ] Virtual environment created successfully
- [ ] Python dependencies installed
- [ ] Frontend builds successfully (dist/ created)
- [ ] PyInstaller creates .exe
- [ ] Inno Setup creates installer (if installed)
- [ ] Installer runs and completes without errors

## Runtime Testing

### Application Launch
- [ ] Application starts without errors
- [ ] All 4 backend processes start (check logs)
- [ ] Frontend server starts on port 8080
- [ ] Browser opens automatically
- [ ] Process monitor is running

### Permission Dialogs
- [ ] Camera permission dialog appears (first run)
- [ ] Notification permission works (macOS)
- [ ] Permission denial shows helpful message

### Backend Services
- [ ] api_server.py running and responding
- [ ] watch.py connects to heart rate monitor (if available)
- [ ] client.py captures screenshots/webcam
- [ ] collate_data.py creates combined files

### Frontend Functionality
- [ ] Form loads correctly
- [ ] Form validation works
- [ ] Task details saved via API
- [ ] Interventions start after form submission
- [ ] Feedback dialog appears (System 2)
- [ ] Assessment form works

### Process Management
- [ ] Ctrl+C gracefully shuts down all processes
- [ ] Process crash triggers automatic restart
- [ ] Log file created in logs/ilgc.log
- [ ] Log contains output from all services

## Installation Testing

### Windows Installer
- [ ] Setup wizard displays correctly
- [ ] Installation completes without errors
- [ ] Desktop shortcut created (if selected)
- [ ] Start Menu entry created
- [ ] Application launches from Start Menu
- [ ] Uninstaller works correctly
- [ ] All files removed after uninstall

### macOS DMG
- [ ] DMG mounts correctly
- [ ] Drag to Applications works
- [ ] App launches from Applications folder
- [ ] Gatekeeper warning can be bypassed
- [ ] App appears in Launchpad

## Cross-Platform Testing

### Network/API
- [ ] API responds on correct port (5000/5002)
- [ ] Frontend can reach backend API
- [ ] CORS headers present

### Data Files
- [ ] details/ directory created
- [ ] feedback/ directory created
- [ ] collated/ directory created
- [ ] interventions/ directory created
- [ ] JSON files written correctly

## GitHub Actions Testing

### Workflow Triggers
- [ ] Workflow triggers on tag push (v*)
- [ ] Manual workflow dispatch works

### Build Jobs
- [ ] Windows build job completes
- [ ] macOS build job completes
- [ ] Artifacts uploaded successfully

### Release Creation
- [ ] GitHub release created
- [ ] All artifacts attached to release
- [ ] Release notes generated

### Download Page
- [ ] GitHub Pages deploys
- [ ] OS detection works
- [ ] Download links functional

## Edge Cases

### Error Handling
- [ ] Missing dependencies show helpful error
- [ ] Port already in use handled gracefully
- [ ] Network errors don't crash app
- [ ] Invalid form data shows validation errors

### Performance
- [ ] App starts within 10 seconds
- [ ] Memory usage reasonable
- [ ] No memory leaks over time
- [ ] CPU usage acceptable

## Final Checklist

- [ ] Version numbers consistent across all files
- [ ] README instructions accurate
- [ ] Download links point to correct releases
- [ ] No debug/test code left in production
- [ ] All sensitive data removed

## Notes

Use this space to document any issues found during testing:

```
Date: 
Tester:
Issues Found:
-
-
-
```
