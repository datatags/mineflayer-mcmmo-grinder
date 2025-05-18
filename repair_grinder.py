from javascript.errors import JavaScriptError
from javascript import require, On, Once
from threading import Event
import random
import json
import sys

mineflayer = require("mineflayer", "4.27.0")
Vec3 = require("vec3")
autoeat = require("mineflayer-auto-eat").loader

def connect_bot():
    with open("config.json") as f:
        config = json.load(f)
    return mineflayer.createBot({
        'auth': 'microsoft',
        'username': config["minecraft_username"],
        'host': config["target_server"],
        'port': config["target_port"],
    })

bot = connect_bot()

iron_block = None
damaged = False
disconnected_event = Event()
ticks_since_damage = 0

def stop():
    bot.quit()
    print("Exiting...")
    disconnected_event.set()

@Once(bot, "spawn")
def onSpawn(_):
    global main_loop
    print("Login successful")
    global iron_block
    bot.loadPlugin(autoeat)
    if count_diamonds() < 1:
        print("Out of diamonds")
        stop()
        return
    bot.autoEat.setOpts({
        'priority': "foodPoints",
        'startAt': 14
    })
    iron_block_id = bot.registry.blocksByName["iron_block"].id
    iron_block = bot.findBlock({ 'matching': iron_block_id })
    if iron_block is None:
        print("Couldn't find cactus or iron block")
        bot.quit()
        return
    print("Waiting for initial damage...")

@On(bot._client, "damage_event")
def onHurt(_, data, meta):
    if data["entityId"] != bot.entity.id:
        return
    global damaged
    global ticks_since_damage
    if not damaged and data["sourceTypeId"] == 2:
        print("\nRegistered damage\n")
        damaged = True
        iron_block_pos = Vec3(iron_block.position.x + 0.5, iron_block.position.y + 1, iron_block.position.z + 0.5)
        bot.lookAt(iron_block_pos)
    check_armor()
    ticks_since_damage = 0
    print(f"Current health: {bot.health}")
    if bot.health <= 6 and bot.food < 20 and not currently_ticking:
        print("Health low, manually triggering eat")
        try:
            bot.autoEat.eat()
        except JavaScriptError:
            print("No food remains, stopping")
            stop()
    if bot.health <= 3:
        print("Health too low, stopping")
        bot.chat("/home home")
        stop()

@On(bot, "physicsTick")
def onTick(_):
    global ticks_since_damage
    ticks_since_damage += 1
    if ticks_since_damage > 200:
        print("Stopped taking damage, disconnecting")
        stop()

@On(bot, "messagestr")
def onMessage(_, message, message_position, json_msg, sender, verified=False):
    if message_position != "game_info":
        print(f"Message: {message}")

@On(bot, "kicked")
def on_kick(_, reason, loggedIn):
    print(f"Kicked from server: {reason}")
    stop()

@On(bot, "end")
def on_end(*args):
    stop()

def get_remaining_durability(item):
    max_durability = item.maxDurability
    damageComp = item.componentMap.get("damage")
    # Damage component disappears when item is at full durability
    if damageComp is None:
        return max_durability
    return max_durability - damageComp["data"]

currently_ticking = False

def check_armor():
    for slot in range(5, 9):
        item = bot.inventory.slots[slot]
        if item is None:
            print("Missing armor piece")
            stop()
            return
        if get_remaining_durability(item) < 10:
            bot.autoEat.disableAuto()
            while bot.autoEat.isEating:
                bot.waitForTicks(1)
            fix_armor(item, slot)
            bot.autoEat.enableAuto()
            diamonds_remaining = count_diamonds()
            if diamonds_remaining < 1:
                print("Out of diamonds")
                stop()
                return
            print(f"{diamonds_remaining} diamonds remaining")

def jitter():
    bot.entity.yaw += (random.random() - 0.5) / 2
    bot.entity.pitch += (random.random() - 0.5) / 2

def fix_armor(item, slot):
    print(f"Now repairing {item.name}")
    bot.moveSlotItem(slot, bot.inventory.hotbarStart + bot.quickBarSlot)
    # Make bot sneak
    bot.setControlState("sneak", True)
    bot.waitForTicks(4)

    bot.activateBlock(iron_block)
    bot.waitForTicks(4)
    bot.activateBlock(iron_block)
    bot.waitForTicks(4)
    bot.updateHeldItem()
    jitter()
    bot.waitForTicks(4)
    bot.setControlState("sneak", False)
    if get_remaining_durability(bot.heldItem) < 16:
        print("Failed to repair item")
        stop()
        return
    bot.moveSlotItem(bot.inventory.hotbarStart + bot.quickBarSlot, slot)
    bot.waitForTicks(4)

def count_diamonds():
    diamond_id = bot.registry.itemsByName["diamond"].id
    diamond_count = 0
    for slot in range(bot.inventory.inventoryStart, bot.inventory.inventoryEnd):
        item = bot.inventory.slots[slot]
        if item and item.type == diamond_id:
            diamond_count += item.count
    return diamond_count

if __name__ == "__main__":
    try:
        while True:
            if disconnected_event.wait(0.2):
                break
    except KeyboardInterrupt:
        print("\nExiting...")
        pass
    sys.exit(0)
