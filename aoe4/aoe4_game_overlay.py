# AoE4 game overlay
import os
from enum import Enum
from threading import Event

from PyQt6.QtWidgets import QComboBox, QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize, Qt

from common.label_display import QLabelSettings
from common.useful_tools import cut_name_length, widget_x_end, widget_y_end
from common.rts_overlay import RTSGameOverlay, scale_int, scale_list_int

from aoe4.aoe4_settings import AoE4OverlaySettings
from aoe4.aoe4_build_order import check_valid_aoe4_build_order
from aoe4.aoe4_request import get_match_data_threading
from aoe4.aoe4_civ_icon import aoe4_civilization_icon


# ID of the panel to display
class PanelID(Enum):
    CONFIG = 0  # Configuration
    BUILD_ORDER = 1  # Display Build Order
    MATCH_DATA = 2  # Display Match Data


class AoE4GameOverlay(RTSGameOverlay):
    """Game overlay application for AoE4"""

    def __init__(self, directory_main: str):
        """Constructor

        Parameters
        ----------
        directory_main    directory where the main file is located
        """
        super().__init__(directory_main=directory_main, name_game='aoe4', settings_name='aoe4_settings.json',
                         settings_class=AoE4OverlaySettings, check_valid_build_order=check_valid_aoe4_build_order,
                         build_order_category_name='civilization')

        self.selected_panel = PanelID.CONFIG  # panel to display

        # civilization selection
        layout = self.settings.layout
        color_default = layout.color_default
        color_background = layout.color_background
        flag_select_size = layout.configuration.flag_select_size

        self.civilization_select = QComboBox(self)
        self.civilization_select.activated.connect(self.update_build_order_display)
        self.civilization_combo_ids = []  # corresponding IDs
        for civ_name, flag_image in aoe4_civilization_icon.items():
            self.civilization_select.addItem(
                QIcon(os.path.join(self.directory_game_pictures, 'civilization_flag', flag_image)), '')
            self.civilization_combo_ids.append(civ_name)
        self.civilization_select.setIconSize(QSize(flag_select_size[0], flag_select_size[1]))

        self.civilization_select.setStyleSheet(
            'QComboBox {' +
            f'background-color: rgb({color_background[0]}, {color_background[1]}, {color_background[2]});' +
            f'color: rgb({color_default[0]}, {color_default[1]}, {color_default[2]});' +
            'border: 0px' +
            '}'
        )
        self.civilization_select.setToolTip('select civilization')
        self.civilization_select.adjustSize()

        # match data
        self.match_data_thread_started = False  # True after the first call to 'get_match_data_threading'
        self.store_match_data = []  # used for url requests in parallel thread
        self.match_data = None  # match data to use
        self.match_data_warnings = []  # warnings related to match data not found

        self.match_data_thread_id = None
        self.match_data_stop_flag = Event()
        if self.selected_username is not None:
            self.match_data_thread_id = get_match_data_threading(
                self.store_match_data, stop_event=self.match_data_stop_flag, search_input=self.selected_username,
                timeout=self.settings.url_timeout)
            self.match_data_thread_started = True

        self.update_panel_elements()  # update the current panel elements

    def reload(self, update_settings):
        """Reload the application settings, build orders...

        Parameters
        ----------
        update_settings   True to update (reload) the settings, False to keep the current ones
        """
        super().reload(update_settings=update_settings)

        # civilization selection
        layout = self.settings.layout
        color_default = layout.color_default
        color_background = layout.color_background
        flag_select_size = layout.configuration.flag_select_size

        self.civilization_select.setIconSize(QSize(flag_select_size[0], flag_select_size[1]))
        self.civilization_select.setStyleSheet(
            'QComboBox {' +
            f'background-color: rgb({color_background[0]}, {color_background[1]}, {color_background[2]});' +
            f'color: rgb({color_default[0]}, {color_default[1]}, {color_default[2]});' +
            'border: 0px' +
            '}'
        )
        self.civilization_select.adjustSize()

        # game parameters
        print('Reloading parameters and last game data from aoeiv.net...')
        self.match_data = None  # match data to use
        self.match_data_warnings = []  # warnings related to match data not found

        self.update_panel_elements()  # update the current panel elements

    def settings_scaling(self):
        """Apply the scaling on the settings"""
        super().settings_scaling()
        assert 0 <= self.scaling_input_selected_id < len(self.scaling_input_combo_ids)
        layout = self.settings.layout
        unscaled_layout = self.unscaled_settings.layout
        scaling = self.scaling_input_combo_ids[self.scaling_input_selected_id] / 100.0

        layout.configuration.flag_select_size = scale_list_int(
            scaling, unscaled_layout.configuration.flag_select_size)
        layout.match_data.image_width = scale_int(scaling, unscaled_layout.match_data.image_width)

    def quit_application(self):
        """Quit the application"""
        super().quit_application()

        self.match_data_stop_flag.set()
        if self.match_data_thread_id is not None:
            self.match_data_thread_id.join()

        self.close()

    def mousePressEvent(self, event):
        """Actions related to the mouse pressing events

        Parameters
        ----------
        event    mouse event
        """
        if self.selected_panel == PanelID.CONFIG:  # only needed when in configuration mode
            self.build_order_click_select(event)

    def mouseMoveEvent(self, event):
        """Actions related to the mouse moving events

        Parameters
        ----------
        event    mouse event
        """
        if self.selected_panel == PanelID.CONFIG:  # only needed when in configuration mode
            self.move_window(event)

    def update_panel_elements(self):
        """Update the elements of the panel to display"""
        if self.selected_panel != PanelID.CONFIG:
            QApplication.restoreOverrideCursor()
        else:
            QApplication.setOverrideCursor(Qt.ArrowCursor)

        # window is transparent to mouse events, except for the configuration when not hidden
        self.setAttribute(Qt.WA_TransparentForMouseEvents, self.hidden or (self.selected_panel != PanelID.CONFIG))

        # remove the window title and stay always on top
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # hide the elements by default
        self.hide_elements()

        if self.selected_panel == PanelID.CONFIG:  # Configuration
            self.config_panel_layout()
            self.build_order_search.setFocus()
        elif self.selected_panel == PanelID.BUILD_ORDER:  # Build Order
            self.update_build_order()
        elif self.selected_panel == PanelID.MATCH_DATA:  # Display Match Data
            self.update_match_data_display()

        # show the main window
        self.show()

    def next_panel(self):
        """Select the next panel"""

        # saving the upper right corner position
        if self.selected_panel == PanelID.CONFIG:
            self.save_upper_right_position()

        if self.selected_panel == PanelID.CONFIG:
            self.selected_panel = PanelID.BUILD_ORDER
        elif self.selected_panel == PanelID.BUILD_ORDER:
            self.selected_panel = PanelID.MATCH_DATA
        elif self.selected_panel == PanelID.MATCH_DATA:
            self.selected_panel = PanelID.CONFIG

        if self.selected_panel == PanelID.CONFIG:
            # configuration selected build order
            if self.selected_build_order is not None:
                self.build_order_search.setText(self.selected_build_order_name)

        self.update_panel_elements()  # update the elements of the panel to display
        self.update_position()  # restoring the upper right corner position

    def hide_elements(self):
        """Hide elements"""
        super().hide_elements()

        self.civilization_select.hide()

    def get_age_image(self, age_id: int):
        """Get the image for a requested age

        Parameters
        ----------
        age_id    ID of the age

        Returns
        -------
        age image with path
        """
        if age_id == 1:
            return self.settings.images.age_1
        elif age_id == 2:
            return self.settings.images.age_2
        elif age_id == 3:
            return self.settings.images.age_3
        elif age_id == 4:
            return self.settings.images.age_4
        else:
            return self.settings.images.age_unknown

    def update_build_order_display(self):
        """Update the build order search matching display"""
        civilization_id = self.civilization_select.currentIndex()
        assert 0 <= civilization_id < len(self.civilization_combo_ids)
        self.obtain_build_order_search(
            key_condition={'civilization': self.civilization_combo_ids[civilization_id]})
        self.config_panel_layout()

    def config_panel_layout(self):
        """Layout of the configuration panel"""

        # save corner position
        self.save_upper_right_position()

        # show elements
        self.config_quit_button.show()
        self.config_save_button.show()
        self.config_reload_button.show()
        self.font_size_input.show()
        self.scaling_input.show()
        self.next_panel_button.show()

        self.civilization_select.show()

        self.build_order_title.show()
        self.build_order_search.show()
        self.build_order_selection.show()

        self.username_title.show()
        self.username_search.show()
        self.username_selection.show()

        # adjust the size of the elements
        self.build_order_search.adjustSize()
        self.username_search.adjustSize()

        # configuration buttons
        layout = self.settings.layout
        border_size = layout.border_size
        horizontal_spacing = layout.horizontal_spacing
        vertical_spacing = layout.vertical_spacing
        action_button_size = layout.action_button_size
        action_button_spacing = layout.action_button_spacing

        next_x = border_size
        self.config_quit_button.move(next_x, border_size)
        next_x += action_button_size + action_button_spacing
        self.config_save_button.move(next_x, border_size)
        next_x += action_button_size + action_button_spacing
        self.config_reload_button.move(next_x, border_size)
        next_x += action_button_size + horizontal_spacing
        self.font_size_input.move(next_x, border_size)
        next_x += self.font_size_input.width() + horizontal_spacing
        self.scaling_input.move(next_x, border_size)
        next_x += self.scaling_input.width() + horizontal_spacing
        self.next_panel_button.move(next_x, border_size)
        next_y = border_size + max(action_button_size, self.font_size_input.height(),
                                   self.scaling_input.height()) + vertical_spacing  # next Y position

        # build order selection
        self.build_order_title.move(border_size, next_y)
        next_x = border_size + self.build_order_title.width() + horizontal_spacing

        # civilization selection
        self.civilization_select.move(next_x, next_y)

        if self.civilization_select.height() > self.build_order_title.height():
            self.build_order_title.move(self.build_order_title.x(),
                                        widget_y_end(self.civilization_select) - self.build_order_title.height())
        next_y += max(self.build_order_title.height(), self.civilization_select.height()) + vertical_spacing

        # build order search
        self.build_order_search.move(border_size, next_y)
        next_y += self.build_order_search.height() + vertical_spacing

        if widget_x_end(self.build_order_search) > widget_x_end(self.civilization_select):
            self.civilization_select.move(
                widget_x_end(self.build_order_search) - self.civilization_select.width(),
                self.civilization_select.y())

        self.build_order_selection.update_size_position(init_y=next_y)

        # username selection
        layout_configuration = layout.configuration
        next_x = layout_configuration.search_spacing + max(
            widget_x_end(self.civilization_select), widget_x_end(self.build_order_search),
            self.build_order_selection.x() + self.build_order_selection.row_max_width)

        self.username_title.move(next_x, self.build_order_title.y())
        self.username_search.move(next_x, self.build_order_search.y())
        self.username_selection.update_size_position(init_x=next_x, init_y=next_y)

        max_x = max(widget_x_end(self.next_panel_button),
                    widget_x_end(self.username_title), widget_x_end(self.username_search),
                    self.username_selection.x() + self.username_selection.row_max_width)

        max_y = max(widget_y_end(self.build_order_search),
                    self.build_order_selection.y() + self.build_order_selection.row_total_height,
                    widget_y_end(self.username_search),
                    self.username_selection.y() + self.username_selection.row_total_height)

        # resize main window
        self.resize(max_x + border_size, max_y + border_size)

        # next panel on the top right corner
        self.next_panel_button.move(self.width() - border_size - self.next_panel_button.width(), border_size)

        # update position (in case the size changed)
        self.update_position()

    def build_order_previous_step(self):
        """Select the previous step of the build order"""
        if (self.selected_panel == PanelID.BUILD_ORDER) and super().build_order_previous_step():
            self.update_build_order()  # update the rendering

    def build_order_next_step(self):
        """Select the next step of the build order"""
        if (self.selected_panel == PanelID.BUILD_ORDER) and super().build_order_next_step():
            self.update_build_order()  # update the rendering

    def select_build_order_id(self, build_order_id: int = -1):
        """Select build order ID

        Parameters
        ----------
        build_order_id    ID of the build order, negative to select next build order

        Returns
        -------
        True if valid build order selection
        """
        if self.selected_panel == PanelID.CONFIG:
            if super().select_build_order_id(build_order_id):
                civilization_id = self.civilization_select.currentIndex()
                assert 0 <= civilization_id < len(self.civilization_combo_ids)
                self.obtain_build_order_search(
                    key_condition={'civilization': self.civilization_combo_ids[civilization_id]})
                if build_order_id >= 0:  # directly select in case of clicking
                    self.select_build_order()
                self.config_panel_layout()
                return True
        return False

    def update_build_order(self):
        """Update the build order panel"""

        # clear the elements (also hide them)
        self.build_order_resources.clear()
        self.build_order_notes.clear()

        if self.selected_build_order is None:  # no build order selected
            self.build_order_notes.add_row_from_picture_line(parent=self, line='No build order selected.')

        else:  # valid build order selected
            selected_build_order_content = self.selected_build_order['build_order']

            # select current step
            assert 0 <= self.selected_build_order_step_id < self.selected_build_order_step_count
            selected_step = selected_build_order_content[self.selected_build_order_step_id]
            assert selected_step is not None

            # target resources
            target_resources = selected_step['resources']
            target_food = target_resources['food']
            target_wood = target_resources['wood']
            target_gold = target_resources['gold']
            target_stone = target_resources['stone']
            target_villager = selected_step['villager_count']
            target_population = selected_step['population_count']

            # space between the resources
            spacing = ''
            layout = self.settings.layout
            for i in range(layout.build_order.resource_spacing):
                spacing += ' '

            # display selected step
            self.build_order_step.setText(
                f'Step: {self.selected_build_order_step_id + 1}/{self.selected_build_order_step_count}')

            images = self.settings.images

            # line to display the target resources
            resources_line = images.food + '@ ' + (str(target_food) if (target_food >= 0) else ' ')
            resources_line += spacing + '@' + images.wood + '@ ' + (str(target_wood) if (target_wood >= 0) else ' ')
            resources_line += spacing + '@' + images.gold + '@ ' + (str(target_gold) if (target_gold >= 0) else ' ')
            resources_line += spacing + '@' + images.stone + '@ ' + (
                str(target_stone) if (target_stone >= 0) else ' ')
            if target_villager >= 0:
                resources_line += spacing + '@' + images.villager + '@ ' + str(target_villager)
            if target_population >= 0:
                resources_line += spacing + '@' + images.population + '@ ' + str(target_population)
            if 1 <= selected_step['age'] <= 4:
                resources_line += spacing + '@' + self.get_age_image(selected_step['age'])
            if 'time' in selected_step:  # add time if indicated
                resources_line += '@' + spacing + '@' + self.settings.images.time + '@' + selected_step['time']

            self.build_order_resources.add_row_from_picture_line(parent=self, line=str(resources_line))

            # notes of the current step
            notes = selected_step['notes']
            for note in notes:
                self.build_order_notes.add_row_from_picture_line(parent=self, line=note)

        self.build_order_panel_layout()  # update layout

    def build_order_panel_layout(self):
        """Layout of the Build order panel"""

        # show elements
        if self.selected_build_order is not None:
            self.build_order_step.show()
            self.build_order_previous_button.show()
            self.build_order_next_button.show()
        self.next_panel_button.show()
        self.build_order_notes.show()
        self.build_order_resources.show()

        # size and position
        layout = self.settings.layout
        border_size = layout.border_size
        vertical_spacing = layout.vertical_spacing
        horizontal_spacing = layout.horizontal_spacing
        action_button_size = layout.action_button_size
        action_button_spacing = layout.action_button_spacing
        bo_next_tab_spacing = layout.build_order.bo_next_tab_spacing

        # action buttons
        next_y = border_size + action_button_size + vertical_spacing

        if self.selected_build_order is not None:
            self.build_order_step.adjustSize()
            next_y = max(next_y, border_size + self.build_order_step.height() + vertical_spacing)

        # build order resources
        self.build_order_resources.update_size_position(init_y=next_y)
        next_y += self.build_order_resources.row_total_height + vertical_spacing
        self.build_order_notes.update_size_position(init_y=next_y)

        # resize of the full window
        max_x = border_size + max(
            (self.build_order_step.width() + 3 * action_button_size +
             horizontal_spacing + action_button_spacing + bo_next_tab_spacing),
            self.build_order_resources.row_max_width,
            self.build_order_notes.row_max_width)

        self.resize(max_x + border_size, next_y + self.build_order_notes.row_total_height + border_size)

        # action buttons on the top right corner
        next_x = self.width() - border_size - action_button_size
        self.next_panel_button.move(next_x, border_size)

        if self.selected_build_order is not None:
            next_x -= (action_button_size + bo_next_tab_spacing)
            self.build_order_next_button.move(next_x, border_size)

            next_x -= (action_button_size + action_button_spacing)
            self.build_order_previous_button.move(next_x, border_size)

            next_x -= (self.build_order_step.width() + horizontal_spacing)
            self.build_order_step.move(next_x, border_size)

        # position update to stay with the same upper right corner position
        self.update_position()

    def fetch_game_match_data(self):
        """Fetch the game match data"""
        # only available if valid game parameters and valid username
        if self.selected_username is not None:
            # new tread call can be launched
            if (not self.match_data_thread_started) or (len(self.store_match_data) >= 1):

                # update valid new match found if last url calls are done
                if len(self.store_match_data) >= 1:
                    if self.store_match_data[0] is not None:
                        if self.store_match_data[0].match_id is not None:
                            self.match_data = self.store_match_data[0]
                        elif self.match_data is None:
                            self.match_data_warnings = self.store_match_data[0].warnings
                    self.store_match_data.clear()

                # launch new thread search
                if self.match_data is None:
                    self.match_data_thread_id = get_match_data_threading(
                        self.store_match_data, stop_event=self.match_data_stop_flag,
                        search_input=self.selected_username, timeout=self.settings.url_timeout)
                    self.match_data_thread_started = True
                else:
                    self.match_data_thread_id = get_match_data_threading(
                        self.store_match_data, stop_event=self.match_data_stop_flag,
                        search_input=self.selected_username, timeout=self.settings.url_timeout,
                        last_match_id=self.match_data.match_id, last_data_found=self.match_data.all_data_found)
                    self.match_data_thread_started = True

    def update_match_data_display(self):
        """Display match data panel"""
        self.match_data_display.clear()

        if self.match_data is None:  # user match data not found
            if self.selected_username is None:
                self.match_data_display.add_row_from_picture_line(
                    parent=self, line='No username provided to find match data.')
            else:
                self.match_data_display.add_row_from_picture_line(
                    parent=self, line=f'https://aoeiv.net: No match found (yet) for {self.selected_username}.')
                for warning_comment in self.match_data_warnings:
                    self.match_data_display.add_row_from_picture_line(parent=self, line=warning_comment)
        else:  # valid match available
            single_elo_show = False  # check if single ELO must be shown (at least one player has it on team game)
            for cur_player in self.match_data.players:
                if cur_player.elo_solo is not None:
                    single_elo_show = True
                    break

            layout_match_data = self.settings.layout.match_data  # settings of the match data layout
            max_length = layout_match_data.match_data_max_length  # max length of the data to display

            # separation spaces between elements
            separation = '@'
            for i in range(layout_match_data.resource_spacing):
                separation += ' '
            separation += '@'

            # check player color and rank class are available
            color_available = False
            rank_class_available = False
            for cur_player in self.match_data.players:
                if cur_player.color is not None:
                    color_available = True
                if cur_player.rank_class is not None:
                    rank_class_available = True

            # describe the title row with its settings
            title_line = ''
            title_labels_settings = []

            # player color
            if color_available:
                title_line += ' ' + separation
                title_labels_settings.append(None)
                title_labels_settings.append(None)

            # civilization flag
            title_line += ' '
            title_labels_settings.append(None)

            # player name column, used to display the map name
            if self.match_data.map_name is not None:
                title_line += separation + cut_name_length(self.match_data.map_name, max_length)
            else:
                title_line += separation + cut_name_length('Unknown map', max_length)
            title_labels_settings.append(None)
            title_labels_settings.append(
                QLabelSettings(text_color=layout_match_data.color_map, text_bold=True, text_alignment='left'))

            # single ELO show
            if single_elo_show:
                title_line += separation + 'QM 1v1'
                title_labels_settings.append(None)
                title_labels_settings.append(QLabelSettings(text_color=layout_match_data.color_elo_solo, text_bold=True,
                                                            text_alignment='center'))

            # game type ELO
            if single_elo_show:
                title_line += separation + 'Team'
            else:
                title_line += separation + 'Elo'
            title_labels_settings.append(None)
            title_labels_settings.append(
                QLabelSettings(text_color=layout_match_data.color_elo, text_bold=True, text_alignment='center'))

            # player rank
            title_line += separation + 'Rank'
            title_labels_settings.append(None)
            title_labels_settings.append(
                QLabelSettings(text_color=layout_match_data.color_rank, text_bold=True, text_alignment='center'))

            # player win rate
            title_line += separation + 'Win%'
            title_labels_settings.append(None)
            title_labels_settings.append(
                QLabelSettings(text_color=layout_match_data.color_win_rate, text_bold=True, text_alignment='center'))

            # player wins
            title_line += separation + 'Win'
            title_labels_settings.append(None)
            title_labels_settings.append(
                QLabelSettings(text_color=layout_match_data.color_wins, text_bold=True, text_alignment='center'))

            # player losses
            title_line += separation + 'Loss'
            title_labels_settings.append(None)
            title_labels_settings.append(
                QLabelSettings(text_color=layout_match_data.color_losses, text_bold=True, text_alignment='center'))

            # rank class
            title_line += separation + 'action_button/to_end.png'
            title_labels_settings.append(None)
            title_labels_settings.append(QLabelSettings(image_width=self.next_panel_button.width(),
                                                        text_alignment='center'))

            # display title line
            self.match_data_display.add_row_from_picture_line(parent=self, line=title_line,
                                                              labels_settings=title_labels_settings)

            # loop on the players
            for cur_player in self.match_data.players:
                player_line = ''
                player_labels_settings = []

                # player color
                if color_available:
                    color_str = '?'  # assuming unknown color string
                    color = self.settings.layout.color_default  # use default color

                    color_id = cur_player.color
                    if (color_id is not None) and isinstance(color_id, int):
                        color_str = str(color_id)

                        if color_id == 1:
                            color = layout_match_data.color_player_1
                        elif color_id == 2:
                            color = layout_match_data.color_player_2
                        elif color_id == 3:
                            color = layout_match_data.color_player_3
                        elif color_id == 4:
                            color = layout_match_data.color_player_4
                        elif color_id == 5:
                            color = layout_match_data.color_player_5
                        elif color_id == 6:
                            color = layout_match_data.color_player_6
                        elif color_id == 7:
                            color = layout_match_data.color_player_7
                        elif color_id == 8:
                            color = layout_match_data.color_player_8
                        else:
                            print(f'Unknown color ID {color_id}.')

                    if not isinstance(color, list):
                        print(f'Invalid player color {color}, using the default one.')
                        color = self.settings.layout.color_default

                    player_line += color_str + separation
                    player_labels_settings.append(
                        QLabelSettings(text_alignment='center', text_color=color, text_bold=True))
                    player_labels_settings.append(None)

                # civilization flag
                if cur_player.civ is not None:
                    player_line += f'civilization_flag/{aoe4_civilization_icon[cur_player.civ]}' if (
                            cur_player.civ in aoe4_civilization_icon) else cur_player.civ
                else:
                    player_line += '?'
                player_labels_settings.append(QLabelSettings(image_width=layout_match_data.image_width,
                                                             image_height=layout_match_data.image_height,
                                                             text_alignment='center'))

                # player name
                if cur_player.name is not None:
                    player_line += separation + cut_name_length(cur_player.name, max_length)
                else:
                    player_line += separation + 'Unknown'
                player_labels_settings.append(None)
                player_labels_settings.append(
                    QLabelSettings(text_color=layout_match_data.color_player_name, text_alignment='left'))

                # single ELO show
                if single_elo_show:
                    player_labels_settings.append(None)
                    if cur_player.elo_solo is not None:
                        player_line += separation + str(cur_player.elo_solo)
                        player_labels_settings.append(
                            QLabelSettings(text_color=layout_match_data.color_elo_solo, text_alignment='right'))
                    else:
                        player_line += separation + '-'
                        player_labels_settings.append(
                            QLabelSettings(text_color=layout_match_data.color_elo_solo, text_alignment='center'))

                # game type ELO
                if cur_player.elo is not None:
                    player_line += separation + str(cur_player.elo)
                else:
                    player_line += separation + '-'
                player_labels_settings.append(None)
                player_labels_settings.append(
                    QLabelSettings(text_color=layout_match_data.color_elo, text_alignment='right'))

                # player rank
                if cur_player.rank is not None:
                    player_line += separation + '#' + str(cur_player.rank)
                else:
                    player_line += separation + '-'
                player_labels_settings.append(None)
                player_labels_settings.append(
                    QLabelSettings(text_color=layout_match_data.color_rank, text_alignment='right'))

                # player win rate
                if cur_player.win_rate is not None:
                    player_line += separation + str(cur_player.win_rate) + '%'
                else:
                    player_line += separation + '-'
                player_labels_settings.append(None)
                player_labels_settings.append(
                    QLabelSettings(text_color=layout_match_data.color_win_rate, text_alignment='right'))

                # player wins
                if cur_player.wins is not None:
                    player_line += separation + str(cur_player.wins)
                else:
                    player_line += separation + '-'
                player_labels_settings.append(None)
                player_labels_settings.append(
                    QLabelSettings(text_color=layout_match_data.color_wins, text_alignment='right'))

                # player losses
                if cur_player.losses is not None:
                    player_line += separation + str(cur_player.losses)
                else:
                    player_line += separation + '-'
                player_labels_settings.append(None)
                player_labels_settings.append(
                    QLabelSettings(text_color=layout_match_data.color_losses, text_alignment='right'))

                # rank class
                rank_class_str = ' '
                rank_class = cur_player.rank_class
                if (rank_class is not None) and isinstance(rank_class, str):
                    rank_class_str = os.path.join(self.directory_game_pictures, 'rank', str(rank_class) + '.png')

                player_line += separation + rank_class_str
                player_labels_settings.append(None)
                player_labels_settings.append(QLabelSettings(
                    text_alignment='center', text_bold=True, image_height=layout_match_data.rank_class_height))

                # display player line
                self.match_data_display.add_row_from_picture_line(parent=self, line=player_line,
                                                                  labels_settings=player_labels_settings)

        self.game_match_data_layout()  # update layout

    def game_match_data_layout(self):
        """Layout of the game match panel"""
        self.match_data_display.show()
        self.next_panel_button.show()

        # size and position
        self.match_data_display.update_size_position(adapt_to_columns=True)

        # resize of the full window
        border_size = self.match_data_display.border_size

        width = 2 * border_size + self.match_data_display.row_max_width
        if self.match_data is None:  # increase size for the next frame button
            width += self.settings.layout.horizontal_spacing + self.settings.layout.action_button_size

        self.resize(width, 2 * border_size + self.match_data_display.row_total_height)

        # next panel on the top right corner
        self.next_panel_button.move(self.width() - border_size - self.next_panel_button.width(), border_size)
        self.next_panel_button.raise_()  # raise to the top of the parent widget's stack

        # update position (in case the size changed)
        self.update_position()

    def timer_mouse_keyboard_call(self):
        """Function called on a timer (related to mouse and keyboard inputs)"""
        super().timer_mouse_keyboard_call()

        if self.selected_panel == PanelID.CONFIG:  # configuration specific buttons
            self.config_quit_button.hovering_show(self.is_mouse_in_roi_widget)
            self.config_save_button.hovering_show(self.is_mouse_in_roi_widget)
            self.config_reload_button.hovering_show(self.is_mouse_in_roi_widget)

        elif self.selected_panel == PanelID.BUILD_ORDER:  # build order specific buttons
            self.build_order_previous_button.hovering_show(self.is_mouse_in_roi_widget)
            self.build_order_next_button.hovering_show(self.is_mouse_in_roi_widget)

    def timer_match_data_call(self):
        """Function called on a timer (related to match data)"""
        if not self.stop_application:
            self.fetch_game_match_data()

            if self.selected_panel == PanelID.MATCH_DATA:
                self.update_match_data_display()  # layout updated in function

    def enter_key_actions(self):
        """Actions performed when pressing the Enter key"""
        if self.selected_panel == PanelID.CONFIG:
            if self.build_order_search.hasFocus():
                self.select_build_order(key_condition={
                    'civilization': self.civilization_combo_ids[self.civilization_select.currentIndex()]})

            if self.username_search.hasFocus():
                self.select_username()  # update username
                self.fetch_game_match_data()  # launch potential new game search

            self.config_panel_layout()  # update layout
