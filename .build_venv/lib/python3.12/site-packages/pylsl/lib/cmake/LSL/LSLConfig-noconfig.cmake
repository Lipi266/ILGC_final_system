#----------------------------------------------------------------
# Generated CMake target import file.
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "LSL::lsl" for configuration ""
set_property(TARGET LSL::lsl APPEND PROPERTY IMPORTED_CONFIGURATIONS NOCONFIG)
set_target_properties(LSL::lsl PROPERTIES
  IMPORTED_LOCATION_NOCONFIG "${_IMPORT_PREFIX}/lib/liblsl.1.16.2.dylib"
  IMPORTED_SONAME_NOCONFIG "@rpath/liblsl.2.dylib"
  )

list(APPEND _cmake_import_check_targets LSL::lsl )
list(APPEND _cmake_import_check_files_for_LSL::lsl "${_IMPORT_PREFIX}/lib/liblsl.1.16.2.dylib" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
