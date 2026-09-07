; ----------------------------------------------------------------------------
; str8-led-eq.inc
; Shared STR8-N / RAM-worker PIA LED status constants.
; Public raw console services do not change the LED display.
; ----------------------------------------------------------------------------

STR8_LED_PIA_PORTA             EQU     $7FA0

STR8_LED_G_RUN                 EQU     $01
STR8_LED_G_HOST                EQU     $02
STR8_LED_G_RX                  EQU     $04
STR8_LED_G_TX                  EQU     $08
STR8_LED_R_FAULT               EQU     $10
STR8_LED_R_NO_HOST             EQU     $20
STR8_LED_R_RX_WAIT             EQU     $40
STR8_LED_R_TX_WAIT             EQU     $80

; Minimal first-slice states. Later slices may compose the individual flags.
STR8_LED_STATUS_RELEASED       EQU     $00
STR8_LED_STATUS_RUNNING        EQU     $01
STR8_LED_STATUS_NO_HOST_WAIT   EQU     $21
STR8_LED_STATUS_INPUT_WAIT     EQU     $41
STR8_LED_STATUS_HOST_INPUT_WAIT EQU    $43
STR8_LED_STATUS_RX_ACTIVITY    EQU     $07
STR8_LED_STATUS_TX_ACTIVITY    EQU     $0B
STR8_LED_STATUS_FLASH_MUTATE   EQU     $F0
