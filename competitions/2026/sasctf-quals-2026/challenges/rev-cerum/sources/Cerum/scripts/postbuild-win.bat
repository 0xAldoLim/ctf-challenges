@echo off

REM - CALL "$(SolutionDir)scripts\postbuild-win.bat" "$(TargetExt)" "$(BINARY_NAME)" "$(Platform)" "$(COPY_VST2)" "$(TargetPath)" "$(VST2_ARM64EC_PATH)" "$(VST2_X64_PATH)" "$(VST3_ARM64EC_PATH)" "$(VST3_X64_PATH)" "$(AAX_ARM64EC_PATH)" "$(AAX_X64_PATH)" "$(CLAP_ARM64EC_PATH)" "$(CLAP_X64_PATH)" "$(BUILD_DIR)" "$(VST_ICON)" "$(AAX_ICON)" "$(CREATE_BUNDLE_SCRIPT)" "$(ICUDAT_PATH)"

set FORMAT=%1
set NAME=%2
set PLATFORM=%3
set COPY_VST2=%4
set BUILT_BINARY=%5
set VST2_ARM64EC_PATH=%6
set VST2_X64_PATH=%7 
set VST3_ARM64EC_PATH=%8
set VST3_X64_PATH=%9
shift
shift 
shift
shift
shift 
shift
shift
set AAX_ARM64EC_PATH=%3
set AAX_X64_PATH=%4
set CLAP_ARM64EC_PATH=%5
set CLAP_X64_PATH=%6
set BUILD_DIR=%7
set VST_ICON=%8
set AAX_ICON=%9
shift
set CREATE_BUNDLE_SCRIPT=%9
shift
set ICUDAT_PATH=%9

REM echo POSTBUILD SCRIPT VARIABLES -----------------------------------------------------
REM echo FORMAT %FORMAT% 
REM echo NAME %NAME% 
REM echo PLATFORM %PLATFORM% 
REM echo COPY_VST2 %COPY_VST2% 
REM echo BUILT_BINARY %BUILT_BINARY% 
REM echo VST2_ARM64EC_PATH %VST2_ARM64EC_PATH% 
REM echo VST2_X64_PATH %VST2_X64_PATH% 
REM echo VST3_ARM64EC_PATH %VST3_ARM64EC_PATH% 
REM echo VST3_X64_PATH %VST3_X64_PATH% 
REM echo CLAP_ARM64EC_PATH %CLAP_ARM64EC_PATH%
REM echo CLAP_X64_PATH %CLAP_X64_PATH% 
REM echo BUILD_DIR %BUILD_DIR%
REM echo VST_ICON %VST_ICON% 
REM echo AAX_ICON %AAX_ICON% 
REM echo CREATE_BUNDLE_SCRIPT %CREATE_BUNDLE_SCRIPT%
REM echo ICUDAT_PATH %ICUDAT_PATH%
REM echo END POSTBUILD SCRIPT VARIABLES -----------------------------------------------------

if %PLATFORM% == "x64" (
  if not exist "%ProgramFiles(x86)%" (
    echo "This batch script fails on 32 bit windows... edit accordingly"
  )
  
  if %FORMAT% == ".vst3" (
    echo copying 64bit binary to VST3 BUNDLE ...
    call %CREATE_BUNDLE_SCRIPT% %BUILD_DIR%\%NAME%.vst3 %VST_ICON% %FORMAT%
    copy /y %BUILT_BINARY% %BUILD_DIR%\%NAME%.vst3\Contents\x86_64-win
    if exist "%ICUDAT_PATH%" (
      copy /y %ICUDAT_PATH% %BUILD_DIR%\%NAME%.vst3\Contents\x86_64-win
    )
    if exist %VST3_X64_PATH% (
      echo copying VST3 bundle to 64bit VST3 Plugins folder ...
      call %CREATE_BUNDLE_SCRIPT% %VST3_X64_PATH%\%NAME%.vst3 %VST_ICON% %FORMAT%
      xcopy /E /H /Y %BUILD_DIR%\%NAME%.vst3\Contents\*  %VST3_X64_PATH%\%NAME%.vst3\Contents\
    )
  )
)

python ..\scripts\rtti_obfuscator.py -o ..\build-win\vst3\x64\Release\Cerum.vst3 ..\build-win\vst3\x64\Release\Cerum.vst3
